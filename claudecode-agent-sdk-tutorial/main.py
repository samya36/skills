from claude_agent_sdk import query
from os.path import join, dirname

from claude_agent_sdk.client import ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
from dotenv import load_dotenv
import asyncio
import contextlib
import sys
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live

# Import custom tools
from tools import greet, get_current_time, get_time_now

dot_envpath = join(dirname(__file__), ".env")
load_dotenv(dot_envpath)
console = Console()


def display_message(msg):
    """Standardized message display function with Rich UI.

    - UserMessage: Panel with yellow border
    - AssistantMessage: Panel with green border (text and tool calls)
    - SystemMessage: ignored
    - ResultMessage: Panel with blue border showing stats
    """
    if isinstance(msg, UserMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                console.print(
                    Panel(
                        f"[bold yellow]{block.text}",
                        title="User",
                        border_style="yellow",
                    )
                )
    elif isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                console.print(
                    Panel(
                        f"[bold green]{block.text}",
                        title="Claude",
                        border_style="green",
                    )
                )
            elif isinstance(block, ToolUseBlock):
                # Display tool calls with magenta border
                tool_info = f"[bold magenta]Tool:[/bold magenta] {block.name}\n"
                tool_info += f"[bold magenta]Input:[/bold magenta] {block.input}"
                console.print(
                    Panel(
                        tool_info,
                        title=f"🔧 Tool Call: {block.name}",
                        border_style="magenta",
                    )
                )
    elif isinstance(msg, SystemMessage):
        # Ignore system messages
        pass
    elif isinstance(msg, ResultMessage):
        # ResultMessage stats are now only shown in /status command
        pass


async def example_basic_streaming():
    """Basic streaming with context manager."""
    console.print(Panel("[bold cyan]Claude Code Agent Demo", border_style="cyan"))

    # Show initializing spinner
    spinner = Live(
        Spinner("dots", text="Initializing...", style="cyan"),
        console=console,
        refresh_per_second=10,
    )
    spinner.start()

    # Create custom tools MCP server
    custom_tools = create_sdk_mcp_server(
        name="custom_tools",
        version="1.0.0",
        tools=[
            greet,
            get_current_time,
            get_time_now,
        ],
    )

    # Configure options with MCP server and allowed tools
    options = ClaudeAgentOptions(
        mcp_servers={
            "tools": custom_tools,
            "Playwright": {
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest", "--extension"],
            },
        },
        permission_mode="bypassPermissions",
        allowed_tools=[
            "WebSearch",
            "WebFetch",
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "mcp__tools__greet",
            "mcp__tools__get_current_time",
            "mcp__tools__get_time_now",
        ],
        max_buffer_size=10 * 1024 * 1024,  # 10MB buffer limit
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Stop spinner after client is fully initialized
            spinner.stop()
            console.print(
                "[dim]Commands: /help | /status | /exit (or press Ctrl+C)[/dim]\n"
            )

            # Store latest session stats
            latest_stats = {
                "session_id": None,
                "duration_ms": None,
                "total_cost_usd": None,
                "usage": None,
            }

            while True:
                # Get query from user input with styled prompt
                console.print()
                console.print("[bold yellow]>[/bold yellow] ", end="")
                user_query = input().strip()

                # Skip empty queries
                if not user_query:
                    continue

                # Handle special commands
                if user_query.startswith("/"):
                    command = user_query.lower()

                    # Exit commands
                    if command in ["/exit", "/quit", "/q"]:
                        console.print(
                            Panel("[bold green]Goodbye! 👋", border_style="green")
                        )
                        break

                    # Help command
                    elif command in ["/help", "/h"]:
                        help_text = """[cyan]Available Commands:[/cyan]

[yellow]/help[/yellow] or [yellow]/h[/yellow]      - Show this help message
[yellow]/status[/yellow] or [yellow]/stat[/yellow] - Show session statistics
[yellow]/exit[/yellow] or [yellow]/quit[/yellow]   - Exit the chat
[yellow]exit[/yellow] or [yellow]quit[/yellow]     - Exit the chat

[cyan]Custom Tools:[/cyan]
• greet - Greet a user
• get_current_time - Get time in a specific timezone
• get_time_now - Get current local time"""
                        console.print(
                            Panel(help_text, title="Help", border_style="cyan")
                        )
                        continue

                    # Status command
                    elif command in ["/status", "/stat"]:
                        status_text = f"""[cyan]Session Information:[/cyan]

Session ID: {latest_stats["session_id"] or "N/A"}
Model: Claude Sonnet 4.5

[cyan]Latest Response Stats:[/cyan]"""

                        # Add duration if available
                        if latest_stats["duration_ms"] is not None:
                            status_text += (
                                f"\nDuration: {latest_stats['duration_ms']}ms"
                            )

                        # Add cost if available
                        if latest_stats["total_cost_usd"] is not None:
                            status_text += (
                                f"\nCost: ${latest_stats['total_cost_usd']:.6f}"
                            )

                        # Add usage details if available
                        if latest_stats["usage"] is not None:
                            usage = latest_stats["usage"]
                            status_text += f"\n\n[cyan]Token Usage:[/cyan]"
                            if isinstance(usage, dict):
                                if "input_tokens" in usage:
                                    status_text += f"\n• Input: {usage['input_tokens']}"
                                if "output_tokens" in usage:
                                    status_text += (
                                        f"\n• Output: {usage['output_tokens']}"
                                    )
                                if "cache_creation_input_tokens" in usage:
                                    status_text += f"\n• Cache Creation: {usage['cache_creation_input_tokens']}"
                                if "cache_read_input_tokens" in usage:
                                    status_text += f"\n• Cache Read: {usage['cache_read_input_tokens']}"

                        status_text += f"""

[cyan]Available Tools:[/cyan]
• WebSearch, WebFetch
• Read, Write, Edit, Bash
• Glob, Grep
• Custom: greet, get_current_time, get_time_now"""

                        console.print(
                            Panel(status_text, title="Status", border_style="blue")
                        )
                        continue

                    # Unknown command
                    else:
                        console.print(f"[red]Unknown command: {user_query}[/red]")
                        console.print("[dim]Type /help for available commands[/dim]")
                        continue

                # Check for exit commands (without /)
                if user_query.lower() in ["exit", "quit", "q"]:
                    console.print(
                        Panel("[bold green]Goodbye! 👋", border_style="green")
                    )
                    break

                # Display user query with Rich Panel (using "You asked" title)
                console.print(
                    Panel(
                        f"[bold yellow]{user_query}",
                        title="You asked",
                        border_style="yellow",
                    )
                )

                await client.query(user_query)

                # Show thinking spinner
                thinking_spinner = Live(
                    Spinner("dots", text="Thinking...", style="cyan"),
                    console=console,
                    transient=True,
                    refresh_per_second=10,
                )
                thinking_spinner.start()

                # Collect all messages first
                async for msg in client.receive_response():
                    display_message(msg)
                    # Save ResultMessage stats for /status command
                    if isinstance(msg, ResultMessage):
                        latest_stats["session_id"] = msg.session_id
                        latest_stats["duration_ms"] = msg.duration_ms
                        latest_stats["total_cost_usd"] = getattr(
                            msg, "total_cost_usd", None
                        )
                        latest_stats["usage"] = getattr(msg, "usage", None)

                # Stop spinner after all messages are rendered
                thinking_spinner.stop()

                console.print()  # Empty line for spacing
    except KeyboardInterrupt:
        console.print("\n")
        console.print(Panel("[bold green]Goodbye! 👋", border_style="green"))


if __name__ == "__main__":
    try:
        asyncio.run(example_basic_streaming())
    except KeyboardInterrupt:
        console.print("\n")
        console.print(Panel("[bold green]Goodbye! 👋", border_style="green"))
# anyio.run(example_basic_streaming)
