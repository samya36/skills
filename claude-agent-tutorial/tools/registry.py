"""Tool registry for managing custom tools."""

from .greet import greet
from .time_tools import get_current_time, get_time_now
from .weather import get_current_weather, get_forecast


# All custom tools
ALL_TOOLS = [
    greet,
    get_current_time,
    get_time_now,
    get_current_weather,
    get_forecast,
]

# Tool names for allowed_tools configuration
TOOL_NAMES = [
    "mcp__tools__greet",
    "mcp__tools__get_current_time",
    "mcp__tools__get_time_now",
    "mcp__tools__get_current_weather",
    "mcp__tools__get_forecast",
]


def get_tools():
    """Get all custom tools.

    Returns:
        List of all custom tool functions
    """
    return ALL_TOOLS


def get_tool_names():
    """Get all tool names for allowed_tools configuration.

    Returns:
        List of tool names with mcp__ prefix
    """
    return TOOL_NAMES
