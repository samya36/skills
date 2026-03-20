"""Display functions for the Claude Agent UI."""

import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
)

console = Console(force_terminal=True, legacy_windows=False)


def _is_skill_loading_message(text: str) -> tuple[bool, str | None, str | None]:
    """Check if a message is a skill loading message.

    Args:
        text: The message text to check

    Returns:
        Tuple of (is_skill_message, skill_name, base_directory)
    """
    # Check if this looks like a skill loading message
    if "Base directory for this skill:" not in text:
        return False, None, None

    lines = text.strip().split('\n')
    base_dir = None

    # Extract base directory - handle both same-line and next-line formats
    for i, line in enumerate(lines):
        if "Base directory for this skill:" in line:
            # Check if path is on the same line (after the colon)
            if ':' in line:
                after_colon = line.split(':', 1)[1].strip()
                if after_colon:  # Path is on same line
                    base_dir = after_colon
                    break

            # Otherwise, check the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line:  # Non-empty next line
                    base_dir = next_line
                    break

    # Extract skill name from the directory path
    skill_name = None
    if base_dir:
        # Extract from path like /path/to/.claude/skills/pdf
        parts = base_dir.split('/')
        if 'skills' in parts:
            skill_idx = parts.index('skills')
            if skill_idx + 1 < len(parts):
                skill_name = parts[skill_idx + 1]

    return True, skill_name, base_dir


def display_message(msg):
    """Standardized message display function with Rich UI.

    - UserMessage: Panel with yellow border
    - AssistantMessage: Panel with green border (text and tool calls)
    - SystemMessage: ignored
    - ResultMessage: Panel with blue border showing stats

    Args:
        msg: Message object to display
    """
    if isinstance(msg, UserMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                # Check if this is a skill loading message
                is_skill, skill_name, base_dir = _is_skill_loading_message(block.text)

                if is_skill:
                    # Display compact version for skill loading
                    skill_text = f"[bold cyan]🔧 Skill loaded:[/bold cyan] [yellow]{skill_name or 'unknown'}[/yellow]"
                    if base_dir:
                        # Show only the last part of the path for brevity
                        skill_text += f"\n[dim]Location: {base_dir}[/dim]"

                    console.print(
                        Panel(
                            skill_text,
                            title="Skill",
                            border_style="cyan",
                            expand=False,
                        )
                    )
                else:
                    # Normal user message display
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
                # Render markdown content
                md = Markdown(block.text)
                console.print(
                    Panel(
                        md,
                        title="Assistant",
                        border_style="green",
                        height=None,  # Don't restrict height
                    )
                )
            elif isinstance(block, ToolUseBlock):
                # Display tool calls with magenta border
                # Format and truncate input for better display
                try:
                    # Try to format as JSON if possible
                    if isinstance(block.input, dict):
                        input_str = json.dumps(block.input, indent=2, ensure_ascii=False)
                    else:
                        input_str = str(block.input)

                    # Truncate very long inputs more safely
                    max_length = 400
                    if len(input_str) > max_length:
                        # Find a safe truncation point (not in the middle of a word or escape)
                        truncate_at = max_length
                        while truncate_at > max_length - 50 and truncate_at > 0:
                            char = input_str[truncate_at - 1:truncate_at]
                            if char in [' ', '\n', ',', '}', ']']:
                                break
                            truncate_at -= 1

                        # Safely truncate and add ellipsis
                        input_str = input_str[:truncate_at].rstrip() + "\n    ...\n  }"

                    # Create formatted text with proper escaping
                    tool_text = Text()
                    tool_text.append("Tool: ", style="bold magenta")
                    tool_text.append(f"{block.name}\n")
                    tool_text.append("Input: ", style="bold magenta")
                    # Ensure the text is properly escaped for Rich
                    tool_text.append(input_str.replace('[', r'\[').replace(']', r'\]'))

                except Exception as e:
                    # Fallback to simple string representation
                    safe_input = str(block.input)[:400].replace('[', r'\[').replace(']', r'\]')
                    tool_text = Text(f"Tool: {block.name}\nInput: {safe_input}...")

                console.print(
                    Panel(
                        tool_text,
                        title=f"🔧 Tool Call: {block.name}",
                        border_style="magenta",
                        expand=False,  # Don't expand to full width
                        width=None,  # Let Rich calculate the width
                        height=None,  # Don't restrict height
                    )
                )
    elif isinstance(msg, SystemMessage):
        # Ignore system messages
        pass
    elif isinstance(msg, ResultMessage):
        # ResultMessage stats are now only shown in /status command
        pass


def show_welcome_panel():
    """Display welcome panel with available commands."""
    console.print(Panel("[bold cyan]Claude Agent Demo", border_style="cyan"))
    console.print(
        "[dim]Commands: /help | /status | /exit (or press Ctrl+C)[/dim]\n"
    )


def show_help():
    """Display help information."""
    help_text = """[cyan]Available Commands:[/cyan]

[yellow]/help[/yellow] or [yellow]/h[/yellow]      - Show this help message
[yellow]/status[/yellow] or [yellow]/stat[/yellow] - Show session statistics
[yellow]/exit[/yellow] or [yellow]/quit[/yellow]   - Exit the chat
[yellow]exit[/yellow] or [yellow]quit[/yellow]     - Exit the chat

[cyan]Custom Tools:[/cyan]
• greet - Greet a user
• get_current_time - Get time in a specific timezone
• get_time_now - Get current local time"""
    console.print(Panel(help_text, title="Help", border_style="cyan"))


def show_status(latest_stats: dict):
    """Display session statistics.

    Args:
        latest_stats: Dictionary containing session statistics
    """
    status_text = f"""[cyan]Session Information:[/cyan]

Session ID: {latest_stats["session_id"] or "N/A"}
Model: Claude Sonnet 4.5

[cyan]Latest Response Stats:[/cyan]"""

    # Add duration if available
    if latest_stats["duration_ms"] is not None:
        status_text += f"\nDuration: {latest_stats['duration_ms']}ms"

    # Add cost if available
    if latest_stats["total_cost_usd"] is not None:
        status_text += f"\nCost: ${latest_stats['total_cost_usd']:.6f}"

    # Add usage details if available
    if latest_stats["usage"] is not None:
        usage = latest_stats["usage"]
        status_text += f"\n\n[cyan]Token Usage:[/cyan]"
        if isinstance(usage, dict):
            if "input_tokens" in usage:
                status_text += f"\n• Input: {usage['input_tokens']}"
            if "output_tokens" in usage:
                status_text += f"\n• Output: {usage['output_tokens']}"
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

    console.print(Panel(status_text, title="Status", border_style="blue"))


def show_goodbye():
    """Display goodbye message."""
    console.print(Panel("[bold green]Goodbye! 👋", border_style="green"))
