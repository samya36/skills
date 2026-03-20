"""TodoTracker for tracking task progress in real-time."""

import time
from typing import Any
from rich.table import Table
from rich.text import Text


class TodoTracker:
    """Tracks todo items and their progress."""

    def __init__(self):
        """Initialize the tracker."""
        self.todos: list[dict[str, Any]] = []
        self.task_start_times: dict[int, float] = {}
        self.task_end_times: dict[int, float] = {}
        self.agent_start_time: float | None = None
        self.current_message_type: str = ""
        self.current_message_preview: str = ""

    def update_todos(self, todos: list[dict[str, Any]]) -> None:
        """Update the todo list from the agent.

        Args:
            todos: List of todo items from the agent
        """
        current_time = time.time()

        # Track when tasks start
        for i, todo in enumerate(todos):
            status = todo.get("status", "pending")

            # Mark start time for newly in-progress tasks
            if status == "in_progress" and i not in self.task_start_times:
                self.task_start_times[i] = current_time

            # Mark end time for newly completed tasks
            if status == "completed" and i not in self.task_end_times:
                self.task_end_times[i] = current_time

        self.todos = todos

    def update_message(self, msg_type: str, msg_preview: str) -> None:
        """Update the current message being processed.

        Args:
            msg_type: Type of message (e.g., "AssistantMessage")
            msg_preview: Preview of the message content
        """
        self.current_message_type = msg_type
        # Clean up preview: strip whitespace, ensure single line
        self.current_message_preview = msg_preview.strip() if msg_preview else ""

    def get_task_time(self, index: int) -> float:
        """Get the elapsed time for a task.

        Args:
            index: Index of the task

        Returns:
            Elapsed time in seconds
        """
        current_time = time.time()

        if index in self.task_end_times:
            # Task completed - return duration
            start = self.task_start_times.get(index, self.agent_start_time or current_time)
            return self.task_end_times[index] - start
        elif index in self.task_start_times:
            # Task in progress - return current duration
            return current_time - self.task_start_times[index]
        else:
            # Task not started
            return 0.0

    def create_table(self, agent_elapsed: float, spinner_state: str = "⠋") -> Table:
        """Create a rich table displaying the current todos.

        Args:
            agent_elapsed: Time elapsed since agent started
            spinner_state: Current spinner character

        Returns:
            Rich Table object
        """
        table = Table(show_header=False, box=None, padding=(0, 0))

        # First row: Timer and message on same line, left-aligned
        # Always show message, truncate to fit (max 80 chars total)
        if self.current_message_preview:
            # Take only first line and truncate if needed
            msg = self.current_message_preview.split('\n')[0][:70]
        else:
            msg = "Waiting for response..."

        header_line = Text()
        header_line.append(f"Agent Execution ({agent_elapsed:.1f}s)", style="bold")
        if msg != "Waiting for response...":
            header_line.append(" - ", style="dim")
            header_line.append(msg, style="dim")
        table.add_row(header_line)

        # Add separator
        table.add_row("")

        # If no todos yet, show current activity
        if not self.todos:
            if self.current_message_type:
                activity_msg = f"{spinner_state} {self.current_message_type}"
                if self.current_message_preview:
                    activity_msg += f": {self.current_message_preview[:50]}..."
            else:
                activity_msg = f"{spinner_state} Processing..."
            table.add_row(Text(activity_msg, style="cyan"))
            return table

        for i, todo in enumerate(self.todos):
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            task_time = self.get_task_time(i)

            # Determine icon based on status
            if status == "completed":
                icon = Text("[✓]", style="green bold")
                time_text = f"({task_time:.1f}s)"
            elif status == "in_progress":
                icon = Text(f"[{spinner_state}]", style="cyan bold")
                time_text = f"({task_time:.1f}s)"
            else:  # pending
                icon = Text("[ ]", style="dim")
                time_text = ""

            # Combine icon, content, and time
            row_text = Text()
            row_text.append(icon)
            row_text.append(f" {content} ")
            if time_text:
                row_text.append(time_text, style="dim")

            table.add_row(row_text)

        return table

    def reset(self) -> None:
        """Reset the tracker for a new query."""
        self.todos = []
        self.task_start_times = {}
        self.task_end_times = {}
        self.agent_start_time = None
        self.current_message_type = ""
        self.current_message_preview = ""
