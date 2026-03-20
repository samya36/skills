#!/usr/bin/env python3
"""Claude Agent Demo - Main Entry Point.

This is a refactored version with clean separation of concerns:
- agents/ - Agent business logic
- ui/ - Display and UI components
- tools/ - Custom tool implementations
"""

from dotenv import load_dotenv
from os.path import join, dirname
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
import asyncio
import time
from claude_agent_sdk.types import ResultMessage, SystemMessage

# Import from refactored modules
from agents import create_agent
from ui import (
    display_message,
    show_welcome_panel,
    show_help,
    show_status,
    show_goodbye,
    TodoTracker,
)

# Load environment variables
dot_envpath = join(dirname(__file__), ".env")
load_dotenv(dot_envpath)
console = Console()


async def run_agent_with_live_ui(agent, tracker, query):
    """Run agent and display live progress UI with real-time messages.

    Args:
        agent: The ClaudeAgent instance
        tracker: The TodoTracker instance
        query: User query string

    Returns:
        List of messages from the agent
    """
    messages = []
    displayed_messages = []  # Track which messages we've shown
    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    spinner_idx = 0
    tracker.agent_start_time = time.time()
    # last_update_time = time.time()
    first_message_received = False
    stream_complete = False

    try:
        # Create the stream first
        stream = agent.stream(query)

        # Process messages in background
        async def process_messages():
            nonlocal first_message_received, stream_complete
            async for msg in stream:
                messages.append(msg)

                # Mark that we've received the first real message
                if not first_message_received and not isinstance(msg, SystemMessage):
                    first_message_received = True

            stream_complete = True

        # Start message processing
        message_task = asyncio.create_task(process_messages())

        # Live UI update loop
        # transient=True replaces content instead of appending
        with Live(console=console, refresh_per_second=10, transient=True) as live:
            # Update spinner animation until stream completes
            while not stream_complete or len(displayed_messages) < len(messages):
                await asyncio.sleep(0.1)  # Update every 100ms

                # Display any new messages above the Live display
                while len(displayed_messages) < len(messages):
                    msg = messages[len(displayed_messages)]
                    displayed_messages.append(msg)

                    # Temporarily stop Live to display message
                    live.stop()
                    display_message(msg)
                    live.start()

                current_time = time.time()
                elapsed = current_time - tracker.agent_start_time
                spinner_state = spinner_frames[spinner_idx % len(spinner_frames)]
                spinner_idx += 1

                # Update the display based on current state
                if tracker.todos:
                    # We have todos, show the todo table with animated spinner
                    table = tracker.create_table(elapsed, spinner_state)
                    live.update(table)
                elif not first_message_received:
                    # Still thinking, show thinking spinner (only if no todos yet)
                    live.update(f"{spinner_state} [cyan]Thinking...[/cyan]")
                else:
                    # Messages received but no todos yet - show processing
                    live.update(f"{spinner_state} [dim]Processing...[/dim]")

        # Wait for message task to complete
        await message_task

        # Show final todo state after Live UI is done (Live was transient)
        if tracker.todos:
            final_elapsed = time.time() - tracker.agent_start_time
            final_table = tracker.create_table(final_elapsed, "✓")
            console.print(final_table)
            console.print()  # Add spacing

    except asyncio.CancelledError:
        # Handle graceful cancellation
        console.print("\n[yellow]Agent execution cancelled.[/yellow]")
        raise
    except Exception as e:
        # Handle other errors
        console.print(f"\n[red]Error during agent execution: {e}[/red]")
        raise

    return messages


async def main():
    """Main interactive loop."""

    # Show welcome message
    show_welcome_panel()

    # Initialize tracker and agent
    tracker = TodoTracker()
    agent = create_agent(
        # todo_callback=tracker.update_todos,
        message_callback=tracker.update_message,
    )

    # Initialize agent client for multi-turn conversations
    await agent.initialize()

    # Session statistics
    latest_stats = {
        "session_id": None,
        "duration_ms": None,
        "total_cost_usd": None,
        "usage": None,
    }

    # Interactive loop
    try:
        while True:
            # Get user input
            console.print()
            console.print("[bold yellow]>[/bold yellow] ", end="")
            user_query = input().strip()

            # Skip empty queries
            if not user_query:
                continue

            # Handle commands
            if user_query.startswith("/"):
                command = user_query.lower()

                # Exit commands
                if command in ["/exit", "/quit", "/q"]:
                    show_goodbye()
                    break

                # Help command
                elif command in ["/help", "/h"]:
                    show_help()
                    continue

                # Status command
                elif command in ["/status", "/stat"]:
                    show_status(latest_stats)
                    continue

                # Unknown command
                else:
                    console.print(f"[red]Unknown command: {user_query}[/red]")
                    console.print("[dim]Type /help for available commands[/dim]")
                    continue

            # Handle exit commands (without /)
            if user_query.lower() in ["exit", "quit", "q"]:
                show_goodbye()
                break

            # Reset tracker for new query
            tracker.reset()

            # Display user query
            console.print(
                Panel(
                    f"[bold yellow]{user_query}",
                    title="You asked",
                    border_style="yellow",
                )
            )

            # Run agent with live UI (messages are displayed in real-time now)
            try:
                messages = await run_agent_with_live_ui(agent, tracker, user_query)
            except asyncio.CancelledError:
                # Agent was cancelled, continue to next query
                console.print("\n[yellow]Agent execution cancelled.[/yellow]")
                continue

            # Just save statistics from ResultMessage (no need to display again)
            for msg in messages:
                if isinstance(msg, ResultMessage):
                    latest_stats["session_id"] = msg.session_id
                    latest_stats["duration_ms"] = msg.duration_ms
                    latest_stats["total_cost_usd"] = getattr(
                        msg, "total_cost_usd", None
                    )
                    latest_stats["usage"] = getattr(msg, "usage", None)

            console.print()  # Empty line for spacing

    except (KeyboardInterrupt, EOFError):
        # Handle graceful exit on Ctrl+C or EOF
        console.print("\n")
        show_goodbye()
    finally:
        # Always cleanup the agent client
        await agent.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n")
        show_goodbye()
    except Exception as e:
        # Handle other exceptions gracefully
        console.print(f"\n[red]Error: {e}[/red]")
    finally:
        # Ensure clean exit
        import sys

        sys.exit(0)
