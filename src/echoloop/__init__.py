"""echoloop — Deepgram audio tools wired to Claude tool-use.

Public API:
- ``transcribe_audio`` / ``speak_text`` / ``analyze_sentiment`` — Deepgram wrappers.
- ``TOOLS`` — Anthropic tool-definition list for the three wrappers.
- ``run_agent`` — Claude tool-use loop over those tools.
- ``DeepgramToolError`` / ``AgentError`` — raised failures callers may catch.
"""

from __future__ import annotations

from .agent import AgentError, run_agent
from .deepgram_tools import (
    DeepgramToolError,
    analyze_sentiment,
    speak_text,
    transcribe_audio,
)
from .schemas import TOOLS

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "transcribe_audio",
    "speak_text",
    "analyze_sentiment",
    "TOOLS",
    "run_agent",
    "DeepgramToolError",
    "AgentError",
]
