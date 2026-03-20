#!/usr/bin/env python3
"""Simple E2B Chat using ClaudeSDKClient.

Interactive chat with Claude running in E2B cloud sandbox,
using ClaudeSDKClient with E2BInteractiveTransport.
"""

import asyncio
import os
import sys
import time
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

# Add reffer path for SDK imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "reffer", "claude-agent-sdk-python", "src"))

from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ToolUseBlock
from claude_agent_sdk.types import ClaudeAgentOptions
from e2b_interactive_transport import E2BInteractiveTransport

load_dotenv()
console = Console()


def create_welcome_panel():
    """Create welcome panel."""
    welcome_text = """
# E2B Chat with ClaudeSDKClient

Chat with Claude running in E2B cloud sandbox

Type your message • `/quit` to exit • `/help` for help
    """
    return Panel(
        Markdown(welcome_text),
        title="[bold cyan]Welcome[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def display_tool_use(tool_block: ToolUseBlock) -> None:
    """Display tool use block with formatting."""
    tool_text = Text()
    tool_text.append("Tool: ", style="bold magenta")
    tool_text.append(f"{tool_block.name}\n")

    # Show input (truncate if too long)
    input_str = str(tool_block.input)
    if len(input_str) > 400:
        input_str = input_str[:400] + "..."

    tool_text.append("Input: ", style="bold magenta")
    tool_text.append(input_str.replace('[', r'\[').replace(']', r'\]'))

    console.print(
        Panel(
            tool_text,
            title=f"🔧 Tool: {tool_block.name}",
            border_style="magenta",
            expand=False,
        )
    )


def create_status_table(transport: E2BInteractiveTransport, turns: int, elapsed: float) -> Table:
    """Create status table."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Status", "[green]connected[/]")
    table.add_row("Sandbox ID", transport.sandbox_id or "N/A")
    table.add_row("Process PID", str(transport.process_pid) if transport.process_pid else "N/A")
    table.add_row("Turns", str(turns))
    table.add_row("Session Time", f"{elapsed:.1f}s")

    return table


async def run_chat():
    """Run interactive chat session."""
    console.clear()
    console.print(create_welcome_panel())

    # Create E2B transport
    transport = E2BInteractiveTransport(
        model=os.getenv("ANTHROPIC_MODEL", "sonnet"),
        max_turns=10,
    )

    # Create SDK client with E2B transport
    client = ClaudeSDKClient(transport=transport)

    turn_count = 0
    start_time = time.time()

    try:
        # Connection phase
        with console.status("[cyan]Connecting to E2B sandbox...", spinner="dots"):
            await client.connect()

        # Show connection success
        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Connected to E2B sandbox\n"
                f"[dim]ID: {transport.sandbox_id}[/dim]\n"
                f"[dim]PID: {transport.process_pid}[/dim]",
                title="[bold green]Connected[/bold green]",
                border_style="green",
            )
        )
        console.print()

        # Chat loop
        while True:
            # Get user input
            console.print()
            try:
                user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            # Handle commands
            if user_input.lower() in ["quit", "exit", "q", "/quit"]:
                break

            if user_input.lower() == "/help":
                console.print()
                console.print(
                    Panel(
                        "[cyan]Commands:[/cyan]\n"
                        "  • Type your message to chat\n"
                        "  • `/quit` or `quit` - Exit the chat\n"
                        "  • `/help` - Show this help\n"
                        "  • `/status` - Show connection status",
                        title="Help",
                        border_style="cyan",
                    )
                )
                continue

            if user_input.lower() == "/status":
                elapsed = time.time() - start_time
                console.print()
                console.print(
                    Panel(
                        create_status_table(transport, turn_count, elapsed),
                        title="[bold cyan]Status[/bold cyan]",
                        border_style="cyan",
                    )
                )
                continue

            # Skip empty input
            if not user_input:
                continue

            # Display user message
            console.print()
            console.print(
                Panel(
                    f"[bold yellow]{user_input}",
                    title="You asked",
                    border_style="yellow",
                )
            )

            # Send message and display response
            turn_count += 1
            console.print()
            console.print(f"[dim]Turn {turn_count}[/dim]")

            try:
                # Send message via SDK client
                with console.status("[cyan]Claude is thinking...", spinner="dots"):
                    await client.query(user_input)

                # Process response messages
                response_text_parts = []

                async for message in client.receive_messages():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                # Collect text
                                response_text_parts.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                # Display tool use
                                display_tool_use(block)

                        # Break after first assistant message
                        # (SDK may yield multiple in streaming scenarios)
                        break

                # Display final response text
                response_text = "\n".join(response_text_parts).strip()
                if response_text:
                    console.print()
                    console.print(
                        Panel(
                            Markdown(response_text),
                            title="Assistant",
                            border_style="green",
                        )
                    )

            except Exception as e:
                console.print(
                    Panel(
                        f"[red]Error: {str(e)}[/red]",
                        title="[bold red]Error[/bold red]",
                        border_style="red",
                    )
                )
                import traceback
                console.print("[dim]")
                traceback.print_exc()
                console.print("[/dim]")

    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[red]{str(e)}[/red]",
                title="[bold red]Connection Error[/bold red]",
                border_style="red",
            )
        )
        import traceback
        console.print("[dim]")
        traceback.print_exc()
        console.print("[/dim]")

    finally:
        # Cleanup
        console.print()
        with console.status("[cyan]Closing connection...", spinner="dots"):
            await client.disconnect()

        # Goodbye message
        elapsed = time.time() - start_time
        console.print()
        console.print(
            Panel(
                f"[cyan]Session completed[/cyan]\n\n"
                f"• Turns: {turn_count}\n"
                f"• Duration: {elapsed:.1f}s\n"
                f"• Sandbox: {transport.sandbox_id or 'N/A'}\n\n"
                f"[bold cyan]Thanks for chatting![/bold cyan]",
                title="[bold cyan]Goodbye[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )


async def main():
    """Main entry point."""
    await run_chat()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
