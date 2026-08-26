# echoloop

**Deepgram speech tools for Claude's tool-use loop. Let Claude transcribe, speak, and read sentiment on demand.**

`echoloop` registers three Deepgram capabilities — speech-to-text (with
summarization), text-to-speech, and audio sentiment — as **Anthropic tool-use
tools**. You hand Claude a message; Claude decides, mid-conversation, which
Deepgram function to call, the call runs, and the result flows back into the
conversation until Claude produces a final answer. You own the loop, inside your
own Python app.

## How this differs from `deepgram-mcp`

Deepgram's official [`deepgram-mcp`](https://pypi.org/project/deepgram-mcp/) is an
**MCP server** that gives AI *editors* (Claude Code, Cursor, Windsurf) access to
Deepgram tools. `echoloop` is the other use case: **Deepgram as Anthropic
tool-use inside your own program**. It is not an MCP server and not for editor
integration.

## Install

Once published to PyPI:

```bash
pip install echoloop
```

From a local clone (development):

```bash
git clone https://github.com/rahat-axes/echoloop-claude-to-deepgram
cd echoloop-claude-to-deepgram
pip install -e .          # add ".[dev]" for pytest/build/twine
```

Requires Python **3.10+**.

## Configuration

Two environment variables are required (see `.env.example`):

```bash
DEEPGRAM_API_KEY=your-deepgram-key
ANTHROPIC_API_KEY=your-anthropic-key
```

Put them in a local `.env` (git-ignored) or export them in your shell.

## The three tools

Each is a plain function you can call directly, and each is also registered with
Claude via `TOOLS`. The audio `source` may be **either a public https URL or a
local file path** — the tool detects which.

| Tool | Signature | Returns |
|------|-----------|---------|
| `transcribe_audio` | `transcribe_audio(source: str)` | `{"transcript": str, "summary": str}` |
| `analyze_sentiment` | `analyze_sentiment(source: str)` | `{"sentiment": str, "score": float}` |
| `speak_text` | `speak_text(text: str, voice="aura-2-thalia-en", out_path="./output.mp3")` | `{"audio_path": str}` |

> **Note:** `speak_text` **saves** the synthesized audio to a file and returns its
> path — it never plays audio. Playback is the caller's choice (this keeps it
> headless-friendly for servers and CI).

## Quickstart

```python
from echoloop import run_agent

# Claude decides which tool(s) to call and summarizes the result.
answer = run_agent(
    "Here's a recording: https://dpgr.am/spacewalk.wav. "
    "Summarize it and tell me the overall sentiment."
)
print(answer)
```

You can also call the tools directly, without Claude:

```python
from echoloop import transcribe_audio, analyze_sentiment, speak_text

print(transcribe_audio("samples/interview.wav"))           # {"transcript": ..., "summary": ...}
print(analyze_sentiment("https://dpgr.am/spacewalk.wav"))  # {"sentiment": "positive", "score": 0.64}
print(speak_text("Hello from echoloop."))                  # writes ./output.mp3
```

## Demo

`demo.py` runs one prompt that forces multiple tools and prints each step:

```bash
python demo.py
```

Abbreviated output:

```
[tool] transcribe_audio
       args:   {"source": "https://dpgr.am/spacewalk.wav"}
       result: {"transcript": "...", "summary": "The speaker reflects on the first all-female spacewalk..."}

[tool] analyze_sentiment
       args:   {"source": "https://dpgr.am/spacewalk.wav"}
       result: {"sentiment": "positive", "score": 0.6363218354015816}

[tool] speak_text
       args:   {"text": "The speaker discusses the historic all-female spacewalk..."}
       result: {"audio_path": "./output.mp3"}

FINAL ANSWER:
Here's a full breakdown: ... (summary + positive sentiment + spoken summary saved to ./output.mp3)
```

## Public API

```python
from echoloop import (
    run_agent,          # the Claude tool-use loop
    TOOLS,              # Anthropic tool definitions for the three tools
    transcribe_audio,
    analyze_sentiment,
    speak_text,
    DeepgramToolError,  # raised on Deepgram failures
    AgentError,         # raised on agent-loop setup failures
)
```

## Development

```bash
pip install -e ".[dev]"
pytest        # fully offline — all network calls are mocked
```

## License

MIT
