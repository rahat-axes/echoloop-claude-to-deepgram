"""Offline unit tests for the echoloop wrappers and agent loop.

All Deepgram and Anthropic network calls are mocked — these tests never touch the
real APIs and require no keys. Run: ``pytest -q``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from echoloop import agent, deepgram_tools
from echoloop.deepgram_tools import DeepgramToolError


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    """Provide dummy API keys so client builders don't reject up front."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an-test")


def _transcribe_response(transcript="hello world", summary="a summary"):
    """Build a mock ListenV1Response with the paths our code reads."""
    resp = MagicMock()
    resp.results.channels[0].alternatives[0].transcript = transcript
    resp.results.summary.short = summary
    return resp


def _sentiment_response(sentiment="positive", score=0.64):
    resp = MagicMock()
    resp.results.sentiments.average.sentiment = sentiment
    resp.results.sentiments.average.sentiment_score = score
    return resp


# --------------------------------------------------------------------------- #
# URL vs local-file detection
# --------------------------------------------------------------------------- #
def test_is_url_detection():
    assert deepgram_tools._is_url("https://x/a.wav") is True
    assert deepgram_tools._is_url("http://x/a.wav") is True
    assert deepgram_tools._is_url("samples/a.wav") is False
    assert deepgram_tools._is_url("/abs/path/a.wav") is False


def test_transcribe_url_routes_to_transcribe_url():
    client = MagicMock()
    client.listen.v1.media.transcribe_url.return_value = _transcribe_response()
    with patch.object(deepgram_tools, "DeepgramClient", return_value=client):
        out = deepgram_tools.transcribe_audio("https://x/a.wav")

    client.listen.v1.media.transcribe_url.assert_called_once()
    kwargs = client.listen.v1.media.transcribe_url.call_args.kwargs
    assert kwargs["url"] == "https://x/a.wav"
    client.listen.v1.media.transcribe_file.assert_not_called()
    assert out == {"transcript": "hello world", "summary": "a summary"}


def test_transcribe_local_reads_bytes_and_uses_transcribe_file(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFFxxxx")
    client = MagicMock()
    client.listen.v1.media.transcribe_file.return_value = _transcribe_response()
    with patch.object(deepgram_tools, "DeepgramClient", return_value=client):
        deepgram_tools.transcribe_audio(str(audio))

    client.listen.v1.media.transcribe_file.assert_called_once()
    kwargs = client.listen.v1.media.transcribe_file.call_args.kwargs
    assert kwargs["request"] == b"RIFFxxxx"  # raw bytes, not the path
    client.listen.v1.media.transcribe_url.assert_not_called()


def test_analyze_sentiment_reads_average():
    client = MagicMock()
    client.listen.v1.media.transcribe_url.return_value = _sentiment_response()
    with patch.object(deepgram_tools, "DeepgramClient", return_value=client):
        out = deepgram_tools.analyze_sentiment("https://x/a.wav")
    assert out == {"sentiment": "positive", "score": pytest.approx(0.64)}


# --------------------------------------------------------------------------- #
# speak_text returns a path and writes a file
# --------------------------------------------------------------------------- #
def test_speak_text_writes_file_and_returns_path(tmp_path):
    out_path = tmp_path / "spoken.mp3"
    client = MagicMock()
    client.speak.v1.audio.generate.return_value = [b"aud", b"io!"]
    with patch.object(deepgram_tools, "DeepgramClient", return_value=client):
        result = deepgram_tools.speak_text("hello", out_path=str(out_path))

    assert result == {"audio_path": str(out_path)}
    assert out_path.exists()
    assert out_path.read_bytes() == b"audio!"


def test_speak_text_rejects_empty_text():
    with pytest.raises(DeepgramToolError):
        deepgram_tools.speak_text("   ")


# --------------------------------------------------------------------------- #
# Errors surface as readable strings
# --------------------------------------------------------------------------- #
def test_missing_deepgram_key_is_clear(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(DeepgramToolError, match="DEEPGRAM_API_KEY"):
        deepgram_tools.transcribe_audio("https://x/a.wav")


def test_sdk_error_wrapped_into_message():
    client = MagicMock()
    client.listen.v1.media.transcribe_url.side_effect = RuntimeError("boom")
    with patch.object(deepgram_tools, "DeepgramClient", return_value=client):
        with pytest.raises(DeepgramToolError, match="boom"):
            deepgram_tools.transcribe_audio("https://x/a.wav")


def test_missing_local_file_is_clear():
    with pytest.raises(DeepgramToolError, match="Could not read audio file"):
        deepgram_tools.transcribe_audio("does/not/exist.wav")


# --------------------------------------------------------------------------- #
# Agent loop: correct dispatch, serialization, callback, error surfacing
# --------------------------------------------------------------------------- #
def _tool_use_block(name, tool_id, tool_input):
    b = MagicMock()
    b.type = "tool_use"
    b.id = tool_id
    b.name = name
    b.input = tool_input
    return b


def _text_response(text):
    b = MagicMock()
    b.type = "text"
    b.text = text
    r = MagicMock()
    r.stop_reason = "end_turn"
    r.content = [b]
    return r


def test_run_agent_dispatches_and_serializes(monkeypatch):
    tu = _tool_use_block("transcribe_audio", "t1", {"source": "https://x/a.wav"})
    r1 = MagicMock()
    r1.stop_reason = "tool_use"
    r1.content = [tu]
    r2 = _text_response("Done.")

    events = []
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [r1, r2]

    monkeypatch.setitem(
        agent._DISPATCH,
        "transcribe_audio",
        lambda source: {"transcript": "hi", "summary": "s"},
    )
    with patch.object(agent, "Anthropic", return_value=fake_client):
        out = agent.run_agent(
            "transcribe it",
            on_tool_call=lambda n, i, r: events.append((n, i, r)),
        )

    assert out == "Done."
    # tool_result serialized as JSON string, tied to the right tool_use id
    second_messages = fake_client.messages.create.call_args_list[1].kwargs["messages"]
    tool_result = second_messages[-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1"
    assert tool_result["content"] == '{"transcript": "hi", "summary": "s"}'
    # callback fired once with the same data
    assert events == [
        ("transcribe_audio", {"source": "https://x/a.wav"}, '{"transcript": "hi", "summary": "s"}')
    ]


def test_run_agent_tool_error_surfaces_as_string(monkeypatch):
    tu = _tool_use_block("transcribe_audio", "t1", {"source": "https://x/a.wav"})
    r1 = MagicMock()
    r1.stop_reason = "tool_use"
    r1.content = [tu]
    r2 = _text_response("Handled.")

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [r1, r2]

    def _boom(source):
        raise DeepgramToolError("deepgram is down")

    monkeypatch.setitem(agent._DISPATCH, "transcribe_audio", _boom)
    with patch.object(agent, "Anthropic", return_value=fake_client):
        out = agent.run_agent("transcribe it")

    assert out == "Handled."
    second_messages = fake_client.messages.create.call_args_list[1].kwargs["messages"]
    tool_result = second_messages[-1]["content"][0]
    assert tool_result["content"] == "Error: deepgram is down"


def test_run_agent_unknown_tool_surfaces_error():
    tu = _tool_use_block("nonexistent", "t9", {})
    r1 = MagicMock()
    r1.stop_reason = "tool_use"
    r1.content = [tu]
    r2 = _text_response("ok")

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [r1, r2]
    with patch.object(agent, "Anthropic", return_value=fake_client):
        agent.run_agent("do something")

    second_messages = fake_client.messages.create.call_args_list[1].kwargs["messages"]
    assert (
        second_messages[-1]["content"][0]["content"]
        == "Error: unknown tool 'nonexistent'."
    )


def test_run_agent_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(agent.AgentError, match="ANTHROPIC_API_KEY"):
        agent.run_agent("hi")
