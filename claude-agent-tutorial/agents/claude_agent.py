"""Claude Agent implementation with SDK integration."""

from typing import Callable, Any, AsyncGenerator
from os import getcwd, getenv
from claude_agent_sdk.client import ClaudeSDKClient
from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
)
from claude_agent_sdk.types import Message, ResultMessage
from tools import get_tools, get_tool_names


class ClaudeAgent:
    """Claude Agent that handles SDK integration and tool management."""

    def __init__(
        self,
        todo_callback: Callable[[list[dict[str, Any]]], None] | None = None,
        message_callback: Callable[[str, str], None] | None = None,
    ):
        """Initialize the Claude Agent.

        Args:
            todo_callback: Callback for todo updates
            message_callback: Callback for message updates
        """
        self.todo_callback = todo_callback
        self.message_callback = message_callback
        self.client: ClaudeSDKClient | None = None  # Persistent client for multi-turn conversations
        self.system_prompt = """You are a helpful assistant that can help with tasks and questions.

GREETING BEHAVIOR:
When a user greets you with "hi", "hello", or similar greetings, ALWAYS use the 'greet' tool to respond. Ask for their name if not provided.

IMPORTANT: When the user includes any of the following in their request:
- "todo" or "TODO"
- "plan step by step" or "step by step"
- "使用 todo" or "todo plan"
- "track progress" or "create a task list"

You MUST use the TodoWrite tool to track your progress throughout the workflow. The TodoWrite tool displays a visual progress tracker for the user.

CRITICAL TodoWrite USAGE:
1. FIRST: Call TodoWrite with all planned tasks (status: "pending") before any work
2. UPDATES: Call TodoWrite to update status as you work:
   - Set to "in_progress" when starting a task
   - Set to "completed" when finishing a task
3. ALWAYS include the COMPLETE todo list in each TodoWrite call
4. Each todo must have these fields:
   - content: Task description (e.g., "Create database schema")
   - activeForm: Present continuous form (e.g., "Creating database schema")
   - status: One of "pending", "in_progress", or "completed"

Example sequence:
```
TodoWrite([
  {"content": "Analyze requirements", "activeForm": "Analyzing requirements", "status": "pending"},
  {"content": "Design solution", "activeForm": "Designing solution", "status": "pending"},
  {"content": "Implement code", "activeForm": "Implementing code", "status": "pending"}
])

```
Remember: Update TodoWrite frequently to show real-time progress to the user."""
        self.options = self._create_options()

    def _setup_mcp_servers(self) -> dict:
        """Setup MCP servers including custom tools.

        Returns:
            Dictionary of MCP server configurations
        """
        # Create custom tools MCP server
        custom_tools = create_sdk_mcp_server(
            name="custom_tools",
            version="1.0.0",
            tools=get_tools(),
        )

        return {
            "tools": custom_tools,
            "Playwright": {
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest", "--extension"],
            },
        }

    async def _post_tool_use_hook(
        self,
        hook_input: HookInput,
        _tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        """Hook callback for PostToolUse events.

        Captures TodoWrite tool calls to extract and report todo lists to the UI.
        """
        # Type guard to check if this is a PostToolUse hook
        if hook_input.get("hook_event_name") != "PostToolUse":
            return {"continue_": True}

        post_tool_use_input = hook_input  # type: ignore[assignment]
        assert isinstance(post_tool_use_input, dict)

        tool_name = post_tool_use_input.get("tool_name")
        tool_input = post_tool_use_input.get("tool_input", {})

        # If this is a TodoWrite call, extract and report the todos
        if tool_name == "TodoWrite" and self.todo_callback:
            todos = tool_input.get("todos", [])
            self.todo_callback(todos)

        # Always allow the tool to proceed
        return {"continue_": True}

    def _setup_hooks(self) -> dict:
        """Setup hooks for tool interception.

        Returns:
            Dictionary of hook configurations
        """
        # Set up hook for all PostToolUse events to capture TodoWrite
        hooks: dict[str, list[HookMatcher]] = {
            "PostToolUse": [
                HookMatcher(
                    matcher=None,  # Capture all tool calls
                    hooks=[self._post_tool_use_hook],
                )
            ]
        }
        return hooks

    def _create_options(self) -> ClaudeAgentOptions:
        """Create ClaudeAgentOptions.

        Returns:
            Configured ClaudeAgentOptions
        """
        # print('model is ',getenv("ANTHROPIC_MODEL", "sonnet"))
        # print('base url is ',getenv("ANTHROPIC_BASE_URL", "sonnet"))
        return ClaudeAgentOptions(
            # env={
            #     "ANTHROPIC_BASE_URL": getenv("ANTHROPIC_BASE_URL", ""),
            #     "ANTHROPIC_API_KEY": getenv("ANTHROPIC_API_KEY", ""),
            #     "ANTHROPIC_MODEL": getenv("ANTHROPIC_MODEL", "sonnet"),
            #     "ANTHROPIC_DEFAULT_HAIKU_MODEL": getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "haiku"),
            # },
            system_prompt=self.system_prompt,
            model=getenv("ANTHROPIC_MODEL", "sonnet"),
            cwd=getcwd(),
            setting_sources=["user", "project"],
            mcp_servers=self._setup_mcp_servers(),
            hooks=self._setup_hooks(),  # Add hooks for TodoWrite tracking
            permission_mode="bypassPermissions",
            allowed_tools=[
                "WebSearch",
                "WebFetch",
                "Read",
                "Skill",
                "Write",
                "Edit",
                "Bash",
                "Glob",
                "Grep",
                "TodoWrite",
            ]
            + get_tool_names(),
            max_buffer_size=10 * 1024 * 1024,  # 10MB buffer limit
        )

    async def initialize(self):
        """Initialize the client session for multi-turn conversations."""
        if self.client is None:
            self.client = ClaudeSDKClient(options=self.options)
            await self.client.__aenter__()

    async def close(self):
        """Close the client session and cleanup resources."""
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def stream(self, query: str) -> AsyncGenerator[Message, None]:
        """Stream messages as they arrive.

        Args:
            query: The user's query

        Yields:
            Messages from the response stream

        Raises:
            Exception: If there's an error during streaming
        """
        # Ensure client is initialized
        if self.client is None:
            await self.initialize()

        try:
            # Reuse the same client for multi-turn conversations
            await self.client.query(query)

            # Stream messages as they arrive
            async for msg in self.client.receive_response():
                # Invoke message callback if available
                if self.message_callback:
                    try:
                        msg_type = type(msg).__name__
                        msg_preview = self._get_message_preview(msg)
                        self.message_callback(msg_type, msg_preview)
                    except Exception as e:
                        # Log callback errors but don't stop streaming
                        print(f"Warning: Message callback error: {e}")

                # Note: TodoWrite detection removed - now handled by PostToolUse hook
                yield msg
        except Exception as e:
            # Re-raise the exception for proper error handling upstream
            raise Exception(f"Streaming error: {e}") from e

    async def run(self, query: str) -> list[Message]:
        """Run a query through the agent and collect all messages.

        Args:
            query: The user's query

        Returns:
            List of all messages from the response
        """
        messages = []
        async for msg in self.stream(query):
            messages.append(msg)
        return messages

    def _get_message_preview(self, msg: Message) -> str:
        """Get a preview of the message content.

        Args:
            msg: The message to preview

        Returns:
            Preview string
        """
        if hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    return block.text[:100]
                elif hasattr(block, "name"):
                    return f"Tool: {block.name}"
        return ""


def create_agent(
    todo_callback: Callable[[list[dict[str, Any]]], None] | None = None,
    message_callback: Callable[[str, str], None] | None = None,
) -> ClaudeAgent:
    """Factory function to create a ClaudeAgent.

    Args:
        todo_callback: Callback for todo updates
        message_callback: Callback for message updates

    Returns:
        Configured ClaudeAgent instance
    """
    return ClaudeAgent(todo_callback, message_callback)
