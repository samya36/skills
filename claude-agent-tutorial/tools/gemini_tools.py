"""Gemini-compatible tool definitions and implementations."""

from datetime import datetime
import pytz
from typing import Any
import os
from pathlib import Path


def get_current_time(timezone: str = "UTC") -> str:
    """Get the current time in the specified timezone.

    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Shanghai')

    Returns:
        Formatted time string
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        iso_format = current_time.isoformat()

        return f"""Current time in {timezone}:
- Formatted: {formatted_time}
- ISO Format: {iso_format}
- Date: {current_time.strftime("%A, %B %d, %Y")}
- Time: {current_time.strftime("%I:%M:%S %p")}
- Timezone offset: {current_time.strftime("%z")}"""
    except pytz.exceptions.UnknownTimeZoneError:
        return f"Error: Unknown timezone '{timezone}'. Please use a valid timezone name like 'UTC', 'America/New_York', 'Asia/Shanghai', etc."
    except Exception as e:
        return f"Error getting current time: {str(e)}"


def get_time_now() -> str:
    """Get the current time in the local timezone.

    Returns:
        Formatted time string
    """
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    iso_format = current_time.isoformat()

    return f"""Current local time:
- Formatted: {formatted_time}
- ISO Format: {iso_format}
- Date: {current_time.strftime("%A, %B %d, %Y")}
- Time: {current_time.strftime("%I:%M:%S %p")}
- Unix timestamp: {int(current_time.timestamp())}"""


def greet(name: str = "friend") -> str:
    """Greet a user with a friendly message.

    Args:
        name: Name of the person to greet

    Returns:
        Greeting message
    """
    return f"Hello {name}! 👋 It's great to meet you. How can I help you today?"


def list_files(directory: str = ".") -> str:
    """List files and directories in the specified directory.

    Args:
        directory: Directory path to list (default is current directory)

    Returns:
        Formatted list of files and directories
    """
    try:
        path = Path(directory).expanduser().resolve()

        if not path.exists():
            return f"Error: Directory '{directory}' does not exist"

        if not path.is_dir():
            return f"Error: '{directory}' is not a directory"

        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

        result = f"Contents of {path}:\n\n"

        for item in items:
            if item.is_dir():
                result += f"📁 {item.name}/\n"
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f}KB"
                else:
                    size_str = f"{size/(1024*1024):.1f}MB"
                result += f"📄 {item.name} ({size_str})\n"

        return result
    except PermissionError:
        return f"Error: Permission denied to access '{directory}'"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def read_file(file_path: str) -> str:
    """Read and return the contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        File contents as string
    """
    try:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return f"Error: File '{file_path}' does not exist"

        if not path.is_file():
            return f"Error: '{file_path}' is not a file"

        # Check file size to prevent reading huge files
        file_size = path.stat().st_size
        if file_size > 1024 * 1024:  # 1MB limit
            return f"Error: File is too large ({file_size/(1024*1024):.1f}MB). Maximum size is 1MB"

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        return f"Contents of {path}:\n\n{content}"
    except UnicodeDecodeError:
        return f"Error: Cannot read '{file_path}' - file appears to be binary"
    except PermissionError:
        return f"Error: Permission denied to read '{file_path}'"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(file_path: str, content: str) -> str:
    """Write content to a file (creates or overwrites).

    Args:
        file_path: Path to the file to write
        content: Content to write to the file

    Returns:
        Success or error message
    """
    try:
        path = Path(file_path).expanduser().resolve()

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        file_size = path.stat().st_size
        return f"Successfully wrote {file_size} bytes to {path}"
    except PermissionError:
        return f"Error: Permission denied to write to '{file_path}'"
    except Exception as e:
        return f"Error writing file: {str(e)}"


# Gemini Tool Registry
# Each tool has a 'definition' (JSON schema) and a 'function' (Python callable)
GEMINI_TOOLS = {
    "get_current_time": {
        "definition": {
            "name": "get_current_time",
            "description": "Get the current time in a specified timezone. Use this when the user asks about the time in a specific location or timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Shanghai', 'Europe/London')",
                    }
                },
                "required": ["timezone"],
            },
        },
        "function": get_current_time,
    },
    "get_time_now": {
        "definition": {
            "name": "get_time_now",
            "description": "Get the current time in the local timezone. Use this when the user asks 'what time is it now' without specifying a timezone.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        "function": get_time_now,
    },
    "greet": {
        "definition": {
            "name": "greet",
            "description": "Greet a user with a friendly message. Use this when the user says hello, hi, or greets you.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the person to greet. If not provided, use 'friend'.",
                    }
                },
                "required": [],
            },
        },
        "function": greet,
    },
    "list_files": {
        "definition": {
            "name": "list_files",
            "description": "List files and directories in a specified directory. Use this when the user wants to see what files are in a folder, or uses commands like 'ls', 'list files', 'show files in directory'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path to list. Can be relative (e.g., '.', './folder') or absolute (e.g., '/Users/bella/projects'). Defaults to current directory if not specified.",
                    }
                },
                "required": [],
            },
        },
        "function": list_files,
    },
    "read_file": {
        "definition": {
            "name": "read_file",
            "description": "Read and return the contents of a text file. Use this when the user wants to see file contents, or uses commands like 'read file', 'show me the file', 'cat', 'view file'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read. Can be relative (e.g., 'README.md', './folder/file.txt') or absolute (e.g., '/Users/bella/projects/file.py').",
                    }
                },
                "required": ["file_path"],
            },
        },
        "function": read_file,
    },
    "write_file": {
        "definition": {
            "name": "write_file",
            "description": "Write content to a file (creates new file or overwrites existing). Use this when the user wants to create a file, save content to a file, or overwrite a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write. Can be relative or absolute. Parent directories will be created if they don't exist.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    }
                },
                "required": ["file_path", "content"],
            },
        },
        "function": write_file,
    },
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get all tool definitions in Gemini format.

    Returns:
        List of tool definition dictionaries
    """
    return [tool["definition"] for tool in GEMINI_TOOLS.values()]


def execute_tool(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Execute a tool by name with the given arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool

    Returns:
        Tool execution result as a string
    """
    if tool_name not in GEMINI_TOOLS:
        return f"Error: Unknown tool '{tool_name}'"

    try:
        tool_function = GEMINI_TOOLS[tool_name]["function"]
        result = tool_function(**tool_args)
        return result
    except Exception as e:
        return f"Error executing tool '{tool_name}': {str(e)}"
