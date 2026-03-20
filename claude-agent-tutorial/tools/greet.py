from typing import Any

from claude_agent_sdk import tool


@tool("greet", "Use this tool when user says 'hi' or 'hello' to greet them back.", {})
async def greet(args: dict[str, Any]) -> dict[str, Any]:
    """Greet a user.

    Args:
        args: Dictionary (can be empty)

    Returns:
        A dictionary with greeting message
    """
    name = args.get("name", "")
    if name:
        return {"content": [{"type": "text", "text": f"Hello 你好, {name}!"}]}
    else:
        return {"content": [{"type": "text", "text": "Hi! 你好! How can I help you today?"}]}
