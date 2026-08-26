"""Claude tool-use loop wiring the Deepgram wrappers to the Messages API.

``run_agent`` sends a user message to Claude with the Deepgram ``TOOLS``
registered, executes any tools Claude calls, feeds the results back, and returns
Claude's final text. Confirmed against anthropic 1.0.0 block shapes — see
``claude/NOTES.md``.
"""

from __future__ import annotations

import json
import os
from typing import Callable, Optional

from anthropic import Anthropic

from .deepgram_tools import (
    DeepgramToolError,
    analyze_sentiment,
    speak_text,
    transcribe_audio,
)
from .schemas import TOOLS

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# tool name -> wrapper. Keys must match the schema `name`s in schemas.py.
_DISPATCH = {
    "transcribe_audio": transcribe_audio,
    "analyze_sentiment": analyze_sentiment,
    "speak_text": speak_text,
}


class AgentError(Exception):
    """Raised for problems setting up or running the agent loop itself."""


def _client() -> Anthropic:
    """Build an Anthropic client from ``ANTHROPIC_API_KEY``."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AgentError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env file."
        )
    return Anthropic(api_key=api_key)


def _run_tool(name: str, tool_input: dict) -> str:
    """Dispatch a single tool call and return its result serialized as a string.

    Tool failures are returned as readable text (not raised) so the loop can hand
    them back to Claude as a ``tool_result`` and let it recover.
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."
    try:
        result = fn(**tool_input)
    except DeepgramToolError as exc:
        return f"Error: {exc}"
    except TypeError as exc:
        return f"Error: bad arguments for '{name}': {exc}"
    return json.dumps(result)


def _final_text(content) -> str:
    """Concatenate the text blocks of a response into one string."""
    return "".join(
        block.text for block in content if getattr(block, "type", None) == "text"
    )


def run_agent(
    user_message: str,
    *,
    max_turns: int = 6,
    on_tool_call: Optional[Callable[[str, dict, str], None]] = None,
) -> str:
    """Run the Claude tool-use loop for a single user message.

    Claude may call the Deepgram tools zero or more times; their results are fed
    back until Claude produces a final answer or ``max_turns`` is reached.

    If ``on_tool_call`` is given, it is invoked once per tool as
    ``on_tool_call(name, tool_input, result)`` where ``result`` is the serialized
    tool output — useful for logging/demo output. It never affects the loop.

    Returns Claude's final text.
    """
    client = _client()
    messages: list[dict] = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return _final_text(response.content)

        # Echo Claude's turn (raw content blocks) back into the conversation.
        messages.append({"role": "assistant", "content": response.content})

        # Run every tool Claude requested and collect one tool_result each.
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tool_input = dict(block.input)
            result = _run_tool(block.name, tool_input)
            if on_tool_call is not None:
                on_tool_call(block.name, tool_input, result)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    # Hit the turn cap without a final answer — make one last call and return
    # whatever text Claude gives, so the caller always gets a string.
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=TOOLS,
        messages=messages,
    )
    return _final_text(response.content)
