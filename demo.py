"""echoloop demo — Claude driving Deepgram tools end to end.

Sends one prompt that forces multiple tools (transcribe -> sentiment -> speak),
prints each tool call as Claude makes it, then prints the final answer. The
terminal output of this script doubles as the project's demo clip / screenshot.

Usage:
    python demo.py                 # default multi-tool prompt
    python demo.py "<your prompt>" # custom prompt

NOTE: makes real Anthropic + Deepgram API calls (a few cents) and writes
./output.mp3 via the speak_text tool.
"""

from __future__ import annotations

import json
import os
import sys

from echoloop import run_agent

AUDIO_URL = "https://dpgr.am/spacewalk.wav"
DEFAULT_PROMPT = (
    f"Here's a recording: {AUDIO_URL}. Summarize what was said, tell me the "
    "overall sentiment, then produce a spoken version of the summary."
)


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so the API keys are available without sourcing."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return  # no .env — rely on the existing environment
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _print_tool_call(name: str, tool_input: dict, result: str) -> None:
    """Callback: print each tool Claude invokes, with its args and result."""
    print(f"\n[tool] {name}")
    print(f"       args:   {json.dumps(tool_input)}")
    print(f"       result: {result}")


def main(argv: list[str]) -> int:
    prompt = argv[0] if argv else DEFAULT_PROMPT
    _load_dotenv()

    print("=" * 70)
    print("PROMPT:")
    print(prompt)
    print("=" * 70)

    final = run_agent(prompt, on_tool_call=_print_tool_call)

    print("\n" + "=" * 70)
    print("FINAL ANSWER:")
    print(final)
    print("=" * 70)

    if os.path.exists("output.mp3"):
        size = os.path.getsize("output.mp3")
        print(f"\nSpoken summary saved to ./output.mp3 ({size} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
