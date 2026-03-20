from typing import Any
from datetime import datetime
import pytz
from claude_agent_sdk import tool


@tool("get_current_time", "Get the current time in a specified timezone", {"timezone": str})
async def get_current_time(args: dict[str, Any]) -> dict[str, Any]:
    """Get the current time in the specified timezone.

    Args:
        args: Dictionary containing 'timezone' key

    Returns:
        A dictionary with the current time information
    """
    timezone_name = args.get("timezone", "UTC")

    try:
        # Get timezone object
        tz = pytz.timezone(timezone_name)

        # Get current time in that timezone
        current_time = datetime.now(tz)

        # Format the time in multiple ways
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        iso_format = current_time.isoformat()

        result_text = f"""Current time in {timezone_name}:
- Formatted: {formatted_time}
- ISO Format: {iso_format}
- Date: {current_time.strftime("%A, %B %d, %Y")}
- Time: {current_time.strftime("%I:%M:%S %p")}
- Timezone offset: {current_time.strftime("%z")}"""

        return {
            "content": [{
                "type": "text",
                "text": result_text
            }]
        }
    except pytz.exceptions.UnknownTimeZoneError:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: Unknown timezone '{timezone_name}'. Please use a valid timezone name like 'UTC', 'America/New_York', 'Asia/Shanghai', etc."
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error getting current time: {str(e)}"
            }]
        }


@tool("get_time_now", "Get the current time in local timezone (no arguments needed)", {})
async def get_time_now(args: dict[str, Any]) -> dict[str, Any]:
    """Get the current time in the local timezone.

    Args:
        args: Empty dictionary (no arguments needed)

    Returns:
        A dictionary with the current time information
    """
    # Get current local time
    current_time = datetime.now()

    # Format the time in multiple ways
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    iso_format = current_time.isoformat()

    result_text = f"""Current local time:
- Formatted: {formatted_time}
- ISO Format: {iso_format}
- Date: {current_time.strftime("%A, %B %d, %Y")}
- Time: {current_time.strftime("%I:%M:%S %p")}
- Unix timestamp: {int(current_time.timestamp())}"""

    return {
        "content": [{
            "type": "text",
            "text": result_text
        }]
    }
