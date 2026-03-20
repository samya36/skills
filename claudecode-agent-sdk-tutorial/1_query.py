import asyncio
from os.path import join, dirname

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from dotenv import load_dotenv

dot_envpath = join(dirname(__file__), ".env")
load_dotenv(dot_envpath)


async def main():
    async for message in query(prompt="What is 2 + 2? and which model are you using?"):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")


asyncio.run(main())
