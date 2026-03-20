"""E2B Interactive Transport - Real streaming multi-turn conversation support.

This implementation uses E2B's send_stdin() capability for true interactive
communication with a long-running Claude process.

Key features:
- Single Claude process for entire conversation (not one per message)
- Uses --input-format stream-json (true streaming mode)
- Sends messages to running process via send_stdin()
- Receives responses via stdout/stderr callbacks
- No need to extract session ID
- Implements Transport protocol for Claude Agent SDK integration
"""

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Optional
from dotenv import load_dotenv


from claude_agent_sdk import Transport
from claude_agent_sdk.types import ClaudeAgentOptions
from e2b_code_interpreter import AsyncSandbox

logger = logging.getLogger(__name__)

SANDBOX_AUTO_PAUSE_TIMEOUT = 300  # 5 minutes
# Load environment variables from .env file
load_dotenv()
# Try to get SDK version
try:
    import sys
    from pathlib import Path

    sys.path.insert(
        0, str(Path(__file__).parent / "reffer" / "claude-agent-sdk-python" / "src")
    )
    from claude_agent_sdk._version import __version__ as sdk_version
except ImportError:
    sdk_version = "unknown"


class E2BInteractiveTransport(Transport):
    """E2B Transport with true interactive streaming support.

    This transport starts a single long-running Claude process and communicates
    with it via stdin/stdout for efficient multi-turn conversations.

    Example:
        >>> transport = E2BInteractiveTransport()
        >>> await transport.connect()
        >>>
        >>> # First turn
        >>> response1 = await transport.send_message("Hello! My name is Alice.")
        >>> print(response1)  # "Hello Alice! Nice to meet you..."
        >>>
        >>> # Second turn - same process, maintains context
        >>> response2 = await transport.send_message("What's my name?")
        >>> print(response2)  # "Your name is Alice."
        >>>
        >>> await transport.close()
    """

    def __init__(
        self,
        prompt: Optional[str] = None,
        options: Optional[ClaudeAgentOptions] = None,
        # Backward compatibility parameters
        sandbox_id: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_turns: Optional[int] = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        user: Optional[str] = None,
        stderr_callback: Optional[callable] = None,
    ):
        """Initialize E2B interactive transport.

        Args:
            prompt: Initial prompt string (optional, for SubprocessCLITransport compatibility)
            options: ClaudeAgentOptions object containing model, max_turns, etc.
                    If provided, configuration will be extracted from it. This is the recommended approach.
            # Backward compatibility parameters
            sandbox_id: Existing sandbox ID to reuse (optional)
            api_key: E2B API key (defaults to E2B_API_KEY environment variable)
            model: Claude model to use (e.g., 'claude-sonnet-4-5-20250929')
                   Used as fallback for options.model in options mode
            max_turns: Maximum turns per message (Claude Code setting)
                      Used as fallback for options.max_turns in options mode
            env: Additional environment variables for the sandbox
            cwd: Working directory for the Claude process
            user: User to run Claude as (default: "user")
            stderr_callback: Callback function for stderr output

        Recommended Usage (new approach):
            >>> # Recommended: Pass options at construction time, like SubprocessCLITransport
            >>> options = ClaudeAgentOptions(
            >>>     model="claude-sonnet-4-5-20250929",
            >>>     max_turns=50,
            >>>     system_prompt="You are an expert Python developer",
            >>>     permission_mode='acceptEdits'
            >>> )
            >>> transport = E2BInteractiveTransport(
            >>>     prompt="",  # E2BInteractiveTransport is long-running, no initial prompt needed
            >>>     options=options,  # All config passed via options
            >>> )
            >>> async with ClaudeSDKClient(options=options, transport=transport) as client:
            >>>     ...

        Backward Compatible Usage:
            >>> # Legacy approach: Set parameters directly in constructor
            >>> transport = E2BInteractiveTransport(
            >>>     model="claude-sonnet-4-5-20250929",
            >>>     max_turns=50,
            >>> )
            >>> options = ClaudeAgentOptions(
            >>>     system_prompt="You are an expert Python developer",
            >>>     permission_mode='acceptEdits',
            >>> )
            >>> async with ClaudeSDKClient(options=options, transport=transport) as client:
            >>>     ...

        Parameter Priority (highest to lowest):
            1. Parameters in options (recommended)
            2. Direct constructor parameters (backward compatible)
            3. Default values (Claude CLI defaults)

        Design Notes:
            E2BInteractiveTransport inherits from the Transport base class, which does not
            enforce options handling. The current implementation supports two parameter
            passing methods for backward compatibility, but using a unified approach is recommended.

            - When using ClaudeSDKClient, configure via ClaudeAgentOptions
            - When using E2BInteractiveTransport directly, pass parameters directly
            - When mixing approaches, options parameters take priority

        Legacy Usage:
            >>> # Legacy constructor parameter approach (still supported)
            >>> transport = E2BInteractiveTransport(
            >>>     model="claude-sonnet-4-5-20250929",
            >>>     max_turns=50
            >>> )
            >>> async with ClaudeSDKClient(transport=transport) as client:
            >>>     ...
        """
        # Handle two modes of initialization
        if options is not None:
            # New mode: Use options parameter like SubprocessCLITransport
            # Extract from options with fallback to direct parameters
            self._options = options
            self._sandbox_id = sandbox_id
            self._api_key = api_key or os.getenv("E2B_API_KEY")
            self._model = model or (options.model if options else None)
            self._max_turns = max_turns or (options.max_turns if options else None)
            self._env = env or (options.env if options else {})
            self._cwd = cwd or (options.cwd if options else None)
            self._user = user or (options.user if options else "user")
            self._stderr_callback = stderr_callback
        else:
            # Backward compatibility mode: Use direct parameters
            self._options = None
            self._sandbox_id = sandbox_id
            self._api_key = api_key or os.getenv("E2B_API_KEY")
            self._model = model
            self._max_turns = max_turns
            self._env = env or {}
            self._cwd = cwd
            self._user = user or "user"
            self._stderr_callback = stderr_callback

        # Runtime state
        self._sandbox: Optional[AsyncSandbox] = None
        self._process = None  # Running Claude process
        self._ready = False
        self._stdin_closed = False

        # Message queues
        self._stdout_queue: asyncio.Queue[str] = asyncio.Queue()
        self._stderr_queue: asyncio.Queue[str] = asyncio.Queue()
        self._messages_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Background tasks
        self._parser_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

    def set_options(self, options: ClaudeAgentOptions) -> None:
        """Set ClaudeAgentOptions, allowing runtime configuration from SDK.

        This method enables InternalClient to pass configuration when creating
        transport via (prompt, options), similar to SubprocessCLITransport.

        Args:
            options: ClaudeAgentOptions containing model, max_turns, etc.
        """
        self._options = options
        print(f"[E2B Transport] set_options called: model={options.model}, max_turns={options.max_turns}")
        logger.info(f"[E2B Transport] Options set: model={options.model}, max_turns={options.max_turns}")

    def _get_effective_model(self) -> Optional[str]:
        """Get the effective model parameter.

        Parameter priority:
        1. options.model (if options provided)
        2. Constructor model parameter
        3. None (use Claude CLI default)

        Returns:
            Effective model name or None
        """
        # First, try options.model
        if self._options and hasattr(self._options, 'model') and self._options.model:
            return self._options.model

        # Then, try constructor parameter
        if self._model:
            return self._model

        # Finally, return None (use default)
        return None

    def _get_effective_max_turns(self) -> Optional[int]:
        """Get the effective max_turns parameter.

        Parameter priority:
        1. options.max_turns (if options provided)
        2. Constructor max_turns parameter
        3. None (no limit)

        Returns:
            Maximum turns count or None
        """
        # First, try options.max_turns
        if self._options and hasattr(self._options, 'max_turns') and self._options.max_turns is not None:
            return self._options.max_turns

        # Then, try constructor parameter
        if self._max_turns is not None:
            return self._max_turns

        # Finally, return None (no limit)
        return None

    async def connect(self) -> None:
        """Create sandbox and start Claude process.

        Raises:
            RuntimeError: If sandbox creation or Claude startup fails
        """
        if self._ready:
            return

        self._stdin_closed = False

        try:
            # Create or connect to sandbox
            if self._sandbox_id:
                print(f"[E2B Interactive] Connecting to sandbox: {self._sandbox_id}")
                self._sandbox = await AsyncSandbox.connect(
                    sandbox_id=self._sandbox_id,
                    api_key=self._api_key,
                    timeout=SANDBOX_AUTO_PAUSE_TIMEOUT,
                )
            else:
                print(
                    "[E2B Interactive] Creating new sandbox (anthropic-claude-code)..."
                )

                # Prepare environment variables
                envs = {
                    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
                }
                if os.getenv("ANTHROPIC_BASE_URL"):
                    envs["ANTHROPIC_BASE_URL"] = os.getenv("ANTHROPIC_BASE_URL")
                if os.getenv("EXA_API_KEY"):
                    envs["EXA_API_KEY"] = os.getenv("EXA_API_KEY")

                # Merge user environment variables
                envs.update(self._env)

                self._sandbox = await AsyncSandbox.create(
                    template="anthropic-claude-code",
                    api_key=self._api_key,
                    envs=envs,
                    timeout=SANDBOX_AUTO_PAUSE_TIMEOUT,
                    mcp={
                        "exa": {
                            "apiKey": os.getenv("EXA_API_KEY"),
                        }
                    },
                )

            print(f"[E2B Interactive] ✓ Sandbox ready: {self._sandbox.sandbox_id}")

            # Start Claude process
            await self._start_claude_process()

            # Start parser task
            self._parser_task = asyncio.create_task(self._parse_stdout())

            # Start monitor task
            loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._monitor_process())

            self._ready = True
            logger.info("E2B interactive transport connected")

        except Exception as exc:
            raise RuntimeError(f"Connection failed: {exc}") from exc

    async def _start_claude_process(self) -> None:
        """Start long-running Claude process."""
        # Build command
        cmd_parts = ["claude"]

        # Input/output format
        cmd_parts.extend(["--input-format", "stream-json"])
        cmd_parts.extend(["--output-format", "stream-json"])
        cmd_parts.append("--verbose")

        # Get effective model parameter
        model = self._get_effective_model()
        if model:
            cmd_parts.extend(["--model", model])
            logger.info(f"Using model: {model}")
        else:
            logger.info("Using default model (Claude CLI default)")

        # Get effective max_turns parameter
        max_turns = self._get_effective_max_turns()
        if max_turns is not None:
            cmd_parts.extend(["--max-turns", str(max_turns)])
            logger.info(f"Using max_turns: {max_turns}")

        # Skip permissions
        cmd_parts.append("--dangerously-skip-permissions")

        command = " ".join(cmd_parts)
        print(f"[E2B Interactive] Starting Claude: {command}")

        # Prepare environment variables
        envs = {
            "CLAUDE_CODE_ENTRYPOINT": "sdk-py",
            "CLAUDE_AGENT_SDK_VERSION": sdk_version,
            "CLAUDE_CODE_SANDBOX": "1",
            "PYTHONUNBUFFERED": "1",
        }
        envs.update(self._env)

        # Setup callbacks
        async def on_stdout(data: str) -> None:
            await self._stdout_queue.put(data)

        async def on_stderr(data: str) -> None:
            if self._stderr_callback:
                try:
                    self._stderr_callback(data)
                except Exception:  # pragma: no cover - defensive
                    pass

        cwd = self._cwd or "/home/user"

        # Start process with stdin and callbacks enabled
        assert self._sandbox is not None
        self._process = await self._sandbox.commands.run(
            command,
            background=True,
            stdin=True,
            envs={key: str(value) for key, value in envs.items()},
            cwd=cwd,
            user=self._user,
            timeout=0,  # Don't auto-disconnect long-running process
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )

        print(f"[E2B Interactive] ✓ Claude process started (PID: {self._process.pid})")
        logger.info(f"Claude process started, PID {self._process.pid}")

    async def _monitor_process(self) -> None:
        """Monitor Claude process for completion or errors."""
        try:
            while self._ready and self._process:
                # Check if process is still alive
                # Note: E2B doesn't provide direct process status checking
                # We rely on stdout/stderr callbacks and connection state
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Monitor task cancelled")
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            await self._messages_queue.put({"__error__": f"Process monitor error: {e}"})

    async def _parse_stdout(self) -> None:
        """Parse stdout stream and extract JSON messages."""
        buffer = ""

        try:
            while True:
                # Get stdout chunk
                chunk = await self._stdout_queue.get()
                buffer += chunk

                # Process complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        # Parse JSON message
                        message = json.loads(line)
                        await self._messages_queue.put(message)

                    except json.JSONDecodeError:
                        # Skip non-JSON lines (verbose output)
                        print(f"[E2B Interactive] Non-JSON line: {line[:100]}")
                        continue

        except asyncio.CancelledError:
            logger.info("Parser task cancelled")
        except Exception as e:
            logger.error(f"Parse error: {e}")
            await self._messages_queue.put({"__error__": str(e)})

    async def send_message(self, content: str) -> str:
        """Send message and wait for response.

        Args:
            content: User message content

        Returns:
            Claude's response text

        Raises:
            RuntimeError: If transport is not connected
        """
        if not self._ready:
            raise RuntimeError("Transport not connected. Please call connect() first")

        if self._stdin_closed:
            raise RuntimeError("stdin is closed")

        # Build stream-json message
        # Correct format: {"type": "user", "message": {"role": "user", "content": "..."}, "session_id": "..."}
        message = {
            "type": "user",
            "message": {"role": "user", "content": content},
            "session_id": self._sandbox.sandbox_id if self._sandbox else "default",
        }

        # Send to Claude via stdin
        message_json = json.dumps(message) + "\n"
        print(f"[E2B Interactive] Sending message: {content[:50]}...")

        await self._sandbox.commands.send_stdin(self._process.pid, message_json)

        # Collect response
        response_parts = []
        message_complete = False

        while not message_complete:
            # Get next message from queue
            msg = await self._messages_queue.get()

            # Check for errors
            if "__error__" in msg:
                raise RuntimeError(f"Claude error: {msg['__error__']}")

            msg_type = msg.get("type")

            # Handle different message types
            if msg_type == "assistant":
                # Assistant response message (full format)
                message_data = msg.get("message", {})
                content_blocks = message_data.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "text":
                        response_parts.append(block.get("text", ""))
                # Continue waiting for result message
                continue

            elif msg_type == "result":
                # Result message, indicates this turn is complete
                message_complete = True

            elif msg_type == "message":
                # Full message (legacy format, kept for compatibility)
                content_blocks = msg.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "text":
                        response_parts.append(block.get("text", ""))
                message_complete = True

            elif msg_type == "content_block_delta":
                # Streaming text delta
                delta = msg.get("delta", {})
                if delta.get("type") == "text_delta":
                    response_parts.append(delta.get("text", ""))

            elif msg_type == "message_stop":
                # Message end
                message_complete = True

            elif msg_type in (
                "message_start",
                "content_block_start",
                "content_block_stop",
                "system",
            ):
                # Metadata events - continue
                continue

            elif msg_type == "error":
                # Claude error
                error_msg = msg.get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Claude error: {error_msg}")

        response = "".join(response_parts).strip()
        print(
            f"[E2B Interactive] Response ({len(response)} chars): {response[:100]}..."
        )

        return response

    # ========== Transport Protocol Methods ==========

    async def write(self, data: str) -> None:
        """Write raw data to the transport (Transport protocol method).

        Args:
            data: Raw string data to write (typically JSON + newline)
        """
        if not self._ready:
            raise RuntimeError("Transport not connected")

        if self._stdin_closed:
            raise RuntimeError("stdin is closed")

        await self._sandbox.commands.send_stdin(self._process.pid, data)

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read and parse messages from the transport (Transport protocol method).

        Yields:
            Parsed JSON messages from the transport
        """
        return self._read_messages_impl()

    async def _read_messages_impl(self) -> AsyncIterator[dict[str, Any]]:
        """Internal implementation of read_messages."""
        while self._ready:
            try:
                message = await self._messages_queue.get()

                # Check for error marker
                if "__error__" in message:
                    error_msg = message["__error__"]
                    logger.error(f"Transport error: {error_msg}")
                    # Don't yield error, just log it
                    continue

                yield message

            except asyncio.CancelledError:
                logger.info("Message reading cancelled")
                break
            except Exception as e:
                logger.error(f"Error reading message: {e}")
                break

    def is_ready(self) -> bool:
        """Check if transport is ready for communication.

        Returns:
            True if transport is ready to send/receive messages
        """
        return self._ready and not self._stdin_closed

    async def end_input(self) -> None:
        """End the input stream (close stdin for process transports)."""
        if self._stdin_closed:
            return

        # Send EOF
        print("[E2B Interactive] Closing stdin...")
        await self._sandbox.commands.send_stdin(self._process.pid, "")
        self._stdin_closed = True

    # ========== Legacy Methods (for backward compatibility) ==========

    async def send_stdin(self, data: str) -> None:
        """Send raw data to Claude's stdin (legacy method).

        Args:
            data: Raw data to send (should be stream-json format)
        """
        await self.write(data)

    async def close(self) -> None:
        """Close transport and cleanup resources."""
        self._ready = False

        # Cancel background tasks
        for task in [self._parser_task, self._monitor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Kill Claude process
        if self._process and self._sandbox:
            try:
                print(
                    f"[E2B Interactive] Killing Claude process (PID: {self._process.pid})..."
                )
                await self._sandbox.commands.kill(self._process.pid)
            except Exception as e:
                logger.warning(f"Error killing process: {e}")

        # Close sandbox
        if self._sandbox:
            print(f"[E2B Interactive] Closing sandbox {self._sandbox.sandbox_id}...")
            try:
                await self._sandbox.kill()
            except Exception as e:
                logger.warning(f"Error closing sandbox: {e}")
            self._sandbox = None

        self._stdin_closed = True
        logger.info("E2B interactive transport closed")

    async def get_process_info(self) -> dict[str, Any]:
        """Get current process information.

        Returns:
            Dictionary containing process details
        """
        return {
            "sandbox_id": self._sandbox.sandbox_id if self._sandbox else None,
            "process_pid": self._process.pid if self._process else None,
            "is_connected": self._ready,
            "stdin_closed": self._stdin_closed,
        }

    @property
    def sandbox_id(self) -> Optional[str]:
        """Get current sandbox ID."""
        return self._sandbox.sandbox_id if self._sandbox else None

    @property
    def process_pid(self) -> Optional[int]:
        """Get Claude process PID."""
        return self._process.pid if self._process else None


__all__ = ["E2BInteractiveTransport"]
