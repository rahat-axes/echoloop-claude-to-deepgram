"""Anthropic Messages-API tool definitions for the Deepgram wrappers.

Each entry is a tool-definition dict in the shape the Messages API expects
(``name`` / ``description`` / ``input_schema``). ``name`` values MUST match the
dispatch keys in ``agent.py`` and the function names in ``deepgram_tools.py``:
``transcribe_audio``, ``speak_text``, ``analyze_sentiment``.

Descriptions tell Claude *when* to reach for each tool. ``TOOLS`` is the list to
pass as ``tools=`` on ``client.messages.create(...)``.
"""

from __future__ import annotations

# Shared description for the "source" parameter — every audio-input tool accepts
# either a public https URL or a local file path.
_SOURCE_DESCRIPTION = (
    "The audio to process: either a public https URL or a local file path. "
    "The tool detects which and handles both."
)

TRANSCRIBE_AUDIO_TOOL = {
    "name": "transcribe_audio",
    "description": (
        "Transcribe pre-recorded audio to text and produce a short summary. "
        "Use this when the user provides audio (a URL or local file) and wants "
        "the spoken words written out, or wants the audio summarized. Returns "
        "the full transcript and a summary."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": _SOURCE_DESCRIPTION,
            },
        },
        "required": ["source"],
    },
}

ANALYZE_SENTIMENT_TOOL = {
    "name": "analyze_sentiment",
    "description": (
        "Analyze the overall emotional tone (sentiment) of pre-recorded audio. "
        "Use this when the user asks how the speaker sounds or feels, or wants "
        "the sentiment/mood of audio (a URL or local file). Returns a sentiment "
        "label (e.g. 'positive', 'neutral', 'negative') and a numeric score "
        "roughly in the range -1 to 1."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": _SOURCE_DESCRIPTION,
            },
        },
        "required": ["source"],
    },
}

SPEAK_TEXT_TOOL = {
    "name": "speak_text",
    "description": (
        "Synthesize spoken audio from text using text-to-speech and save it to "
        "a file. Use this when the user wants a spoken or audio version of some "
        "text (for example, reading a summary aloud). Saves an MP3 file and "
        "returns its path; it does not play the audio."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to convert to speech.",
            },
            "voice": {
                "type": "string",
                "description": (
                    "Optional Deepgram Aura voice id. Defaults to "
                    "'aura-2-thalia-en' if omitted."
                ),
            },
            "out_path": {
                "type": "string",
                "description": (
                    "Optional output file path for the MP3. Defaults to "
                    "'./output.mp3' if omitted."
                ),
            },
        },
        "required": ["text"],
    },
}

TOOLS = [TRANSCRIBE_AUDIO_TOOL, ANALYZE_SENTIMENT_TOOL, SPEAK_TEXT_TOOL]
