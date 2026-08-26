# NOTES — confirmed SDK signatures & response shapes

Source of truth for the wrappers (Tasks 3–5). Produced by running
`scratch/spike.py` against the **real** APIs on 2026-08-26. Prefer these confirmed
facts over `plan.md` wherever they disagree — the plan was written against older SDKs.

## Environment (confirmed installed)

| Thing        | Value                        |
|--------------|------------------------------|
| Python       | 3.14.4                       |
| deepgram-sdk | **7.7.1** (Fern-generated client — NOT classic `PrerecordedOptions` / `listen.rest.v("1")`) |
| anthropic    | **1.0.0** (major bump; Messages API + tool-use shapes unchanged) |

### Model / voice decisions (Phase 0 items — now confirmed working)
- **Deepgram STT model:** `nova-3` — works with both `summarize="v2"` and `sentiment=True`. ✅
- **Default Aura voice (`speak_text`):** `aura-2-thalia-en` — succeeded, no fallback needed.
  (`aura-asteria-en` kept as a fallback candidate.) ✅
- **Claude model (`agent.py`):** `claude-sonnet-4-6` — reliable tool-use round-trip. ✅

---

## (a) Pre-recorded transcription + summarization

```python
from deepgram import DeepgramClient
client = DeepgramClient(api_key=...)          # kwarg is api_key=
resp = client.listen.v1.media.transcribe_file(
    request=audio_bytes,      # local file: pass raw bytes as `request=`
    model="nova-3",
    summarize="v2",
    smart_format=True,
    punctuate=True,
)
# URL input: client.listen.v1.media.transcribe_url(url=..., model=..., summarize="v2", ...)
```

Return type: `ListenV1Response`. Confirmed paths:

| Data              | Dotted path                                                  |
|-------------------|--------------------------------------------------------------|
| transcript        | `resp.results.channels[0].alternatives[0].transcript`        |
| confidence        | `resp.results.channels[0].alternatives[0].confidence`        |
| **summary**       | `resp.results.summary.short`  (str)                          |
| summary status    | `resp.results.summary.result`  (== `"success"`)              |
| per-word list     | `resp.results.channels[0].alternatives[0].words[i]`          |

- `resp.results.summary` is a `ListenV1ResponseResultsSummary(result=..., short=...)`.
- **Gotcha:** the classic `alternatives[0].summaries` path is **`None`** with `summarize="v2"`.
  Read `results.summary.short`, not `alternatives[...].summaries`.
- Token usage lives at `resp.metadata.summary_info` (`input_tokens` / `output_tokens`).

---

## (b) Aura TTS to a file

```python
stream = client.speak.v1.audio.generate(
    text="...",
    model="aura-2-thalia-en",
    encoding="mp3",
)
with open(out_path, "wb") as f:
    for chunk in stream:      # generate() returns an Iterator[bytes]
        f.write(chunk)
```

- Confirmed: `generate()` yields raw `bytes` chunks; concatenate to disk.
- Spike wrote 26,928 bytes for a one-sentence prompt with `aura-2-thalia-en`. ✅
- `speak_text` must be **save-only / headless** (no playback) — matters for the Phase 2 e2e test.

---

## (c) Audio sentiment

Same call as (a) but with `sentiment=True` (drop/keep `summarize` independently):

```python
resp = client.listen.v1.media.transcribe_file(
    request=audio_bytes, model="nova-3", sentiment=True, smart_format=True,
)
```

Confirmed paths:

| Data                       | Dotted path                                            |
|----------------------------|--------------------------------------------------------|
| **overall sentiment**      | `resp.results.sentiments.average.sentiment`  (e.g. `"positive"`) |
| **overall score**          | `resp.results.sentiments.average.sentiment_score`  (float, e.g. `0.636`) |
| per-segment list           | `resp.results.sentiments.segments[i]` (`.text`, `.sentiment`, `.sentiment_score`) |
| per-word sentiment         | `...alternatives[0].words[i].sentiment` + `.sentiment_score` |

- `resp.results.sentiments` is `SharedSentiments(segments=[...], average=SharedSentimentsAverage(...))`.
- `average.sentiment` is a label string; `average.sentiment_score` is a float in roughly [-1, 1].
- **Gotcha:** `metadata.sentiment_info` was `null` in the summarize-only run — it only
  populates when `sentiment=True` is requested. Don't rely on it to detect availability;
  check `results.sentiments`.

---

## (d) Anthropic Messages API tool-use round-trip (anthropic 1.0.0)

```python
from anthropic import Anthropic
client = Anthropic(api_key=...)

r1 = client.messages.create(
    model="claude-sonnet-4-6", max_tokens=512, tools=TOOLS, messages=messages,
)
# r1.stop_reason == "tool_use" when Claude wants a tool
```

Block shapes confirmed:
- Tool-call block is a `ToolUseBlock` with `.type == "tool_use"`, `.id`, `.name`, `.input` (a dict).
  - New-in-1.0.0 fields present but ignorable: `caller=DirectCaller(type='direct')`, `toolset_name=None`.
- Text block has `.type == "text"` and `.text`.

Closing the loop (confirmed working — `r2.stop_reason == "end_turn"`):

```python
tu = next(b for b in r1.content if getattr(b, "type", None) == "tool_use")
messages.append({"role": "assistant", "content": r1.content})   # echo raw content blocks back
messages.append({"role": "user", "content": [{
    "type": "tool_result",
    "tool_use_id": tu.id,
    "content": json.dumps(result_dict),      # serialise the wrapper's return dict to a str
}]})
r2 = client.messages.create(model="claude-sonnet-4-6", max_tokens=512, tools=TOOLS, messages=messages)
final_text = "".join(b.text for b in r2.content if getattr(b, "type", None) == "text")
```

Loop rule for `run_agent`: keep calling while `stop_reason == "tool_use"`, dispatching each
`tool_use` block by `.name` and appending one `tool_result` per call; stop at `end_turn` or
`max_turns`.

---

## Dispatch keys (must match Task 4 schema `name`s and Task 5 dict)
- `transcribe_audio`  → wrapper over (a)
- `speak_text`        → wrapper over (b)
- `analyze_sentiment` → wrapper over (c)

## Source detection (Task 3)
Wrappers take a `source` that is either an https URL or a local path. Detect with a scheme
check (e.g. `source.startswith(("http://", "https://"))`): URL → `transcribe_url(url=...)`;
otherwise read bytes and use `transcribe_file(request=...)`.
</content>
</invoke>
