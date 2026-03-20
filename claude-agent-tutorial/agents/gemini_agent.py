"""Gemini Agent implementation with tool calling support."""

import os
from typing import Any, AsyncGenerator, Callable

from google import genai
from google.genai import types

from tools.gemini_tools import execute_tool, get_tool_definitions


class GeminiAgent:
    """Gemini Agent that handles tool calling and multi-turn conversations."""

    def __init__(
        self,
        model: str = "gemini-3-pro-preview",
        system_instruction: str = "You are a helpful assistant.",
        message_callback: Callable[[str, str], None] | None = None,
    ):
        """Initialize the Gemini Agent.

        Args:
            model: Gemini model name to use
            system_instruction: System instruction for the agent
            message_callback: Callback for message updates (type, preview)
        """
        self.model = model
        self.system_instruction = system_instruction
        self.message_callback = message_callback
        self.contents: list[dict[str, Any]] = []  # Conversation history

        # Initialize Gemini client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set it in your .env file or environment."
            )

        self.client = genai.Client(api_key=api_key)

        # Get tool definitions
        self.tool_definitions = get_tool_definitions()

    async def initialize(self):
        """Initialize the agent (for compatibility with main.py interface)."""
        # No async initialization needed for Gemini
        pass

    async def close(self):
        """Close the agent (for compatibility with main.py interface)."""
        # No cleanup needed for Gemini
        pass

    def _notify_message(self, msg_type: str, preview: str):
        """Notify message callback if available.

        Args:
            msg_type: Type of message
            preview: Preview of message content
        """
        if self.message_callback:
            try:
                self.message_callback(msg_type, preview)
            except Exception as e:
                print(f"Warning: Message callback error: {e}")

    async def _run_agent_loop(
        self, user_query: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the agent loop with tool calling support.

        This implements the core agent loop:
        1. Send query with tool definitions
        2. Get response from model
        3. If function calls exist, execute them and continue
        4. Yield responses as they come

        Args:
            user_query: User's query string

        Yields:
            Response dictionaries with type and content
        """
        # Add user query to conversation history
        self.contents.append({"role": "user", "parts": [{"text": user_query}]})

        # Configure the generation with tools
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.7,
        )

        # Add tools if available
        if self.tool_definitions:
            config.tools = [types.Tool(function_declarations=self.tool_definitions)]

        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Generate response
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.contents,
                    config=config,
                )
            except Exception as e:
                yield {
                    "type": "error",
                    "content": f"Error calling Gemini API: {str(e)}",
                }
                return

            # Check if we have function calls
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]

                # Check for function calls in the response
                function_calls = []
                if hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            function_calls.append(part.function_call)

                # If we have function calls, execute them
                if function_calls:
                    # Add model's function call request to history
                    self.contents.append(
                        {
                            "role": "model",
                            "parts": candidate.content.parts,
                        }
                    )

                    # Execute each function call
                    function_responses = []
                    for func_call in function_calls:
                        tool_name = func_call.name
                        tool_args = dict(func_call.args) if func_call.args else {}

                        # Notify about tool use
                        self._notify_message("ToolUse", f"Calling {tool_name}")

                        # Yield tool use notification
                        yield {
                            "type": "tool_use",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                        }

                        # Execute the tool
                        result = execute_tool(tool_name, tool_args)

                        # Create function response
                        function_responses.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"result": result},
                            )
                        )

                    # Add function responses to history and continue loop
                    self.contents.append(
                        {
                            "role": "user",
                            "parts": function_responses,
                        }
                    )

                    # Continue to next iteration to get final response
                    continue

                # No function calls - check for text response
                if hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            # Add to conversation history
                            self.contents.append(
                                {
                                    "role": "model",
                                    "parts": [{"text": part.text}],
                                }
                            )

                            # Notify about assistant message
                            self._notify_message("AssistantMessage", part.text[:100])

                            # Yield the text response
                            yield {
                                "type": "text",
                                "content": part.text,
                            }
                            return

            # If we get here without returning, something unexpected happened
            yield {
                "type": "error",
                "content": "No valid response from model",
            }
            return

        # Max iterations reached
        yield {
            "type": "error",
            "content": "Maximum iterations reached in agent loop",
        }

    async def stream(self, query: str) -> AsyncGenerator[dict[str, Any], None]:
        """Stream messages as they arrive.

        Args:
            query: The user's query

        Yields:
            Message dictionaries compatible with the UI

        Raises:
            Exception: If there's an error during streaming
        """
        try:
            async for response in self._run_agent_loop(query):
                yield response
        except Exception as e:
            raise Exception(f"Streaming error: {e}") from e

    async def run(self, query: str) -> list[dict[str, Any]]:
        """Run a query through the agent and collect all messages.

        Args:
            query: The user's query

        Returns:
            List of all message dictionaries from the response
        """
        messages = []
        async for msg in self.stream(query):
            messages.append(msg)
        return messages


def create_gemini_agent(
    model: str = "gemini-3-pro-preview",
    system_instruction: str = "You are a helpful assistant.",
    message_callback: Callable[[str, str], None] | None = None,
) -> GeminiAgent:
    """Factory function to create a GeminiAgent.

    Args:
        model: Gemini model name to use
        system_instruction: System instruction for the agent
        message_callback: Callback for message updates

    Returns:
        Configured GeminiAgent instance
    """
    return GeminiAgent(
        model=model,
        system_instruction=system_instruction,
        message_callback=message_callback,
    )
