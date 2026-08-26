"""Thin, typed wrappers over the Deepgram SDK.

Three tools used by the Claude agent loop:

- ``transcribe_audio``  — pre-recorded STT (Nova-3) with summarization.
- ``speak_text``        — Aura TTS to a file (save-only, no playback).
- ``analyze_sentiment`` — audio-intelligence sentiment on the transcript.

Each function accepts a ``source`` that is either an https URL or a local file
path (detected via a scheme check) and wraps SDK/transport errors into a
``DeepgramToolError`` carrying a clear, human-readable message the agent loop can
hand straight back to Claude.

Confirmed against deepgram-sdk 7.7.1 (Fern-generated client) — see
``claude/NOTES.md`` for the exact call shapes and response paths.
"""

from __future__ import annotations

import os

from deepgram import DeepgramClient

# --- Model / voice defaults (confirmed working in NOTES.md) -----------------
STT_MODEL = "nova-3"
DEFAULT_VOICE = "aura-2-thalia-en"
DEFAULT_OUT_PATH = "./output.mp3"


class DeepgramToolError(Exception):
    """Raised when a Deepgram call fails or a response is missing expected data.

    The message is intended to be shown to Claude verbatim, so it should read as
    a plain explanation of what went wrong rather than a raw stack trace.
    """


def _is_url(source: str) -> bool:
    """True if ``source`` looks like an http(s) URL rather than a local path."""
    return source.startswith(("http://", "https://"))


def _client() -> DeepgramClient:
    """Build a Deepgram client from ``DEEPGRAM_API_KEY``.

    Raises ``DeepgramToolError`` if the key is missing so the failure is a clear
    message rather than an opaque SDK auth error later on.
    """
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise DeepgramToolError(
            "DEEPGRAM_API_KEY is not set. Add it to your environment or .env file."
        )
    return DeepgramClient(api_key=api_key)


def _read_local_bytes(path: str) -> bytes:
    """Read a local audio file into bytes, wrapping filesystem errors."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as exc:
        raise DeepgramToolError(f"Could not read audio file '{path}': {exc}") from exc


def _transcribe(source: str, **options: object):
    """Run pre-recorded transcription for a URL or local path.

    Shared by ``transcribe_audio`` and ``analyze_sentiment``; ``options`` are the
    per-feature flags (e.g. ``summarize="v2"`` or ``sentiment=True``).
    """
    client = _client()
    media = client.listen.v1.media
    try:
        if _is_url(source):
            return media.transcribe_url(url=source, model=STT_MODEL, **options)
        audio_bytes = _read_local_bytes(source)
        return media.transcribe_file(request=audio_bytes, model=STT_MODEL, **options)
    except DeepgramToolError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface any SDK/transport error as text
        raise DeepgramToolError(f"Deepgram transcription failed for '{source}': {exc}") from exc


def transcribe_audio(source: str) -> dict:
    """Transcribe and summarize pre-recorded audio.

    ``source`` may be an https URL or a local file path.

    Returns ``{"transcript": str, "summary": str}``. ``summary`` is empty if the
    summarizer did not return one (e.g. audio too short).
    """
    resp = _transcribe(source, summarize="v2", smart_format=True, punctuate=True)
    try:
        alt = resp.results.channels[0].alternatives[0]
        transcript = alt.transcript or ""
    except (AttributeError, IndexError, TypeError) as exc:
        raise DeepgramToolError(
            f"Unexpected transcription response shape for '{source}': {exc}"
        ) from exc

    # summarize="v2" puts the summary at results.summary.short (not on the
    # alternative). It may be absent for very short clips.
    summary = ""
    summary_obj = getattr(resp.results, "summary", None)
    if summary_obj is not None:
        summary = getattr(summary_obj, "short", None) or ""

    return {"transcript": transcript, "summary": summary}


def analyze_sentiment(source: str) -> dict:
    """Analyze the overall sentiment of pre-recorded audio.

    ``source`` may be an https URL or a local file path.

    Returns ``{"sentiment": str, "score": float}`` where ``sentiment`` is a label
    such as ``"positive"`` and ``score`` is a float roughly in ``[-1, 1]``.
    """
    resp = _transcribe(source, sentiment=True, smart_format=True)
    try:
        average = resp.results.sentiments.average
        sentiment = average.sentiment
        score = float(average.sentiment_score)
    except (AttributeError, TypeError, ValueError) as exc:
        raise DeepgramToolError(
            f"No sentiment data in response for '{source}': {exc}"
        ) from exc

    return {"sentiment": sentiment, "score": score}


def speak_text(
    text: str,
    voice: str = DEFAULT_VOICE,
    out_path: str | None = None,
) -> dict:
    """Synthesize ``text`` to an audio file with Deepgram Aura TTS.

    Writes MP3 audio to ``out_path`` (default ``./output.mp3``) and returns
    ``{"audio_path": str}``. This function is save-only — it never plays audio.
    """
    if not text or not text.strip():
        raise DeepgramToolError("speak_text requires non-empty text to synthesize.")

    destination = out_path or DEFAULT_OUT_PATH
    client = _client()
    try:
        stream = client.speak.v1.audio.generate(
            text=text,
            model=voice,
            encoding="mp3",
        )
        with open(destination, "wb") as f:
            for chunk in stream:  # generate() yields raw bytes chunks
                f.write(chunk)
    except DeepgramToolError:
        raise
    except OSError as exc:
        raise DeepgramToolError(
            f"Could not write synthesized audio to '{destination}': {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface any SDK/transport error as text
        raise DeepgramToolError(f"Deepgram TTS failed: {exc}") from exc

    return {"audio_path": destination}
