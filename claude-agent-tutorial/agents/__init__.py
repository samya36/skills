"""Agents package for both Claude and Gemini agents."""

# Optional imports - only import if dependencies are available
__all__ = []

try:
    from .claude_agent import ClaudeAgent, create_agent
    __all__.extend(["ClaudeAgent", "create_agent"])
except ImportError:
    # Claude SDK not available
    pass

try:
    from .gemini_agent import GeminiAgent, create_gemini_agent
    __all__.extend(["GeminiAgent", "create_gemini_agent"])
except ImportError:
    # Google GenAI not available
    pass
