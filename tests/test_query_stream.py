"""SSE query stream and the pure helpers that clean CrewAI tokens.

The crew kickoff is a scripted CrewStreamingOutput. History is saved through the
real save_query_history function, against the mock session, so no database is opened.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from crewai.types.streaming import CrewStreamingOutput, StreamChunk, StreamChunkType
from fastapi.testclient import TestClient

from app.api.routes.query import (
    ANSWER_STREAM_CITATION_MARKER,
    clean_stream_answer,
    format_sse,
    iter_fallback_tokens,
    parse_stream_citations,
    save_query_history,
    should_force_answer_start,
    strip_answer_wrappers,
)
from app.models.document import DocumentStatus
from tests.factories import (
    COLLECTION_ID,
    USER_ID,
    SessionContext,
    make_collection,
    make_document,
    rows_result,
    scalar_result,
)


def test_format_sse_writes_event_and_json() -> None:
    assert format_sse("token", {"content": "hi"}) == 'event: token\ndata: {"content": "hi"}\n\n'


def test_strip_answer_wrappers_keeps_the_wrapper_that_appears_first() -> None:
    found, text = strip_answer_wrappers("prefix Here is my answer: middle Final answer: end")

    assert found is True
    assert text == "end"


def test_strip_answer_wrappers_removes_preamble() -> None:
    found, text = strip_answer_wrappers("  Final Answer: FINAL_ANSWER_START hello")
    assert found is True
    assert text == "hello"

    found, text = strip_answer_wrappers("intro FINAL_ANSWER_START rest")
    assert found is True
    assert text == "rest"

    found, text = strip_answer_wrappers("  just the answer")
    assert found is False
    assert text == "just the answer"


def test_should_force_answer_start_ignores_short_text_and_react_hints() -> None:
    assert should_force_answer_start("x" * 39) is False
    assert should_force_answer_start("x" * 40) is True
    assert should_force_answer_start("Thought: " + "x" * 40) is False
    assert should_force_answer_start("Action: " + "x" * 40) is False
    assert should_force_answer_start("Action Input: " + "x" * 40) is False


def test_iter_fallback_tokens_splits_late_answers() -> None:
    assert list(iter_fallback_tokens("")) == []
    assert list(iter_fallback_tokens("   ")) == []
    assert list(iter_fallback_tokens("abcdefgh")) == ["abcdefgh"]
    assert list(iter_fallback_tokens("abcdefghi")) == ["abcdefgh", "i"]


def test_clean_stream_answer_drops_wrappers_and_the_citation_trailer() -> None:
    raw = f"Final Answer: hello\n{ANSWER_STREAM_CITATION_MARKER}[{{}}]"
    assert clean_stream_answer(raw) == "hello"
    assert clean_stream_answer("  hello  ") == "hello"


def test_parse_stream_citations_accepts_json_and_rejects_junk() -> None:
    parsed = parse_stream_citations('[{"filename": "a.txt", "chunk_index": 2, "relevance_score": 0.25}] trailing')
    assert parsed == [{"filename": "a.txt", "chunk_index": 2, "relevance_score": 0.25}]

    defaults = parse_stream_citations('[{"filename": "a.txt"}]')
    assert defaults == [{"filename": "a.txt", "chunk_index": 0, "relevance_score": 0.0}]

    recovered = parse_stream_citations('noise [{"filename": "b.md", "chunk_index": 4}]')
    assert recovered[0]["filename"] == "b.md"

    mixed = parse_stream_citations('[1, {"nope": true}, {"filename": "c.txt"}]')
    assert mixed == [{"filename": "c.txt", "chunk_index": 0, "relevance_score": 0.0}]

    assert parse_stream_citations("") == []
    assert parse_stream_citations("   ") == []
    assert parse_stream_citations("not json") == []
    assert parse_stream_citations("[") == []
    assert parse_stream_citations('{"filename": "a.txt"}') == []


@pytest.mark.asyncio
async def test_save_query_history_persists_the_row(mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.query.async_session_maker", lambda: SessionContext(mock_session))

    history = await save_query_history(
        COLLECTION_ID,
        USER_ID,
        "Why?",
        "Because.",
        [{"filename": "a.txt", "chunk_index": 0, "relevance_score": 1.0}],
    )

    assert history.question == "Why?"
    assert history.answer == "Because."
    assert history.collection_id == COLLECTION_ID
    assert history.user_id == USER_ID
    assert history.created_at is not None
    mock_session.add.assert_called_once_with(history)
    mock_session.commit.assert_awaited()
    mock_session.refresh.assert_awaited()


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        event_name = ""
        data: dict = {}
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        events.append((event_name, data))
    return events


def _chunk(content: str, role: str = "SynthesizerAgent", chunk_type: str = "text") -> StreamChunk:
    return StreamChunk(content=content, agent_role=role, chunk_type=StreamChunkType(chunk_type))


def _stream(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    chunks: list[object],
    *,
    documents: list[object] | None = None,
    history: list[object] | None = None,
    collection: object | None = None,
    kickoff_return: object | None = None,
    kickoff_error: Exception | None = None,
    executes: list[MagicMock] | None = None,
) -> tuple[object, MagicMock, list[bool]]:
    if executes is None:
        executes = [
            scalar_result(make_collection() if collection is None else collection),
            rows_result([make_document()] if documents is None else documents),
            rows_result([] if history is None else history),
        ]
    mock_session.execute = AsyncMock(side_effect=executes)
    monkeypatch.setattr("app.api.routes.query.async_session_maker", lambda: SessionContext(mock_session))

    crew = MagicMock()
    calls: list[bool] = []

    def _build(stream: bool = False) -> tuple[MagicMock, MagicMock]:
        calls.append(stream)
        return crew, MagicMock()

    monkeypatch.setattr("app.api.routes.query.build_query_crew", _build)
    if kickoff_error is not None:
        crew.kickoff.side_effect = kickoff_error
    elif kickoff_return is not None:
        crew.kickoff.return_value = kickoff_return
    else:
        crew.kickoff.return_value = CrewStreamingOutput(sync_iterator=iter(chunks))

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query/stream",
        json={"question": "Can I work remotely?"},
    )
    return response, crew, calls


def test_stream_emits_tokens_then_done_with_citations(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citation = '[{"filename": "policy.pdf", "chunk_index": 1, "relevance_score": 0.9}]'
    response, crew, calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("ignore me", role="RetrieverAgent"),
            _chunk("tool", chunk_type="tool_call"),
            SimpleNamespace(content=None, agent_role="SynthesizerAgent", chunk_type=None),
            _chunk(""),
            _chunk(f"FINAL_ANSWER_STARTThe answer is yes.\n{ANSWER_STREAM_CITATION_MARKER}{citation}"),
        ],
        history=[SimpleNamespace(question="Earlier?", answer=None)],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert events[0] == ("status", {"message": "started"})
    assert [name for name, _data in events if name == "token"]
    assert events[-1][0] == "done"
    assert events[-1][1]["answer"] == "The answer is yes."
    assert events[-1][1]["citations"] == [{"filename": "policy.pdf", "chunk_index": 1, "relevance_score": 0.9}]
    assert events[-1][1]["query_id"]
    assert calls == [True]
    chat_history = crew.kickoff.call_args.kwargs["inputs"]["chat_history"]
    assert "Earlier?" in chat_history
    assert chat_history.endswith("Answer: ")


def test_stream_truncates_prior_answers_to_500_characters(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _response, crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk("FINAL_ANSWER_STARTShort.")],
        history=[SimpleNamespace(question="Long?", answer="a" * 600)],
    )

    chat_history = crew.kickoff.call_args.kwargs["inputs"]["chat_history"]
    assert "a" * 500 in chat_history
    assert "a" * 501 not in chat_history


def test_stream_drops_a_wrapper_that_arrives_after_the_start_marker(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("FINAL_ANSWER_START"),
            _chunk("Final Answer:"),
            _chunk("The handbook says yes."),
        ],
    )

    assert _parse_sse(response.text)[-1][1]["answer"] == "The handbook says yes."


def test_stream_holds_a_wrapper_prefix_then_strips_it(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("FINAL_ANSWER_START"),
            _chunk("Final"),
            _chunk(" Answer: The handbook says yes."),
        ],
    )

    done = _parse_sse(response.text)[-1][1]
    assert done["answer"] == "The handbook says yes."
    assert "Final" not in done["answer"]


def test_stream_flushes_a_short_answer_held_for_the_citation_marker(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk("FINAL_ANSWER_START"), _chunk("Hi")],
    )

    events = _parse_sse(response.text)
    tokens = "".join(data["content"] for name, data in events if name == "token")
    assert tokens == "Hi"
    assert events[-1][1]["answer"] == "Hi"
    assert events[-1][1]["citations"] == []


def test_stream_splits_a_citation_payload_across_chunks(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("FINAL_ANSWER_STARTYes"),
            _chunk('\n__CITATIONS_JSON__[{"filename": '),
            _chunk('"policy.pdf", "chunk_index": 0, "relevance_score": 0.4}]'),
        ],
    )

    done = _parse_sse(response.text)[-1][1]
    assert done["answer"] == "Yes"
    assert done["citations"][0]["filename"] == "policy.pdf"


def test_stream_emits_nothing_when_the_marker_is_the_whole_answer(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citation = '[{"filename": "a.txt", "chunk_index": 0, "relevance_score": 1}]'
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("FINAL_ANSWER_START"),
            _chunk(f"{ANSWER_STREAM_CITATION_MARKER}{citation}"),
        ],
    )

    events = _parse_sse(response.text)
    assert [name for name, _data in events if name == "token"] == []
    assert events[-1][1]["answer"] == ""
    assert events[-1][1]["citations"][0]["filename"] == "a.txt"


def test_stream_force_starts_a_long_answer_without_a_wrapper(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentence = "Remote work is allowed on Fridays for every team."
    assert len(sentence) >= 40
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk(sentence)],
    )

    done = _parse_sse(response.text)[-1][1]
    assert done["answer"] == sentence


def test_stream_falls_back_when_the_synthesizer_never_starts(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk("Thought: looking")],
    )

    events = _parse_sse(response.text)
    tokens = "".join(data["content"] for name, data in events if name == "token")
    assert tokens == "Thought: looking"
    assert events[-1][1]["answer"] == "Thought: looking"
    assert events[-1][1]["citations"] == []


def test_stream_fallback_splits_citations_out_of_unparsed_text(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citation = '[{"filename": "notes.md", "chunk_index": 3, "relevance_score": 1}]'
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk(f"Thought: short {ANSWER_STREAM_CITATION_MARKER}{citation}")],
    )

    done = _parse_sse(response.text)[-1][1]
    assert done["answer"] == "Thought: short"
    assert done["citations"][0]["filename"] == "notes.md"


def test_stream_recovers_citations_trimmed_out_of_the_pending_buffer(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citation = '[{"filename": "kept.pdf", "chunk_index": 2, "relevance_score": 0.2}]'
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk(f"{ANSWER_STREAM_CITATION_MARKER}{citation} Thought: " + "y" * 40),
            _chunk("z" * 50),
        ],
    )

    done = _parse_sse(response.text)[-1][1]
    assert done["citations"][0]["filename"] == "kept.pdf"
    assert "z" in done["answer"]


def test_stream_trims_a_long_react_preamble(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [
            _chunk("Thought: " + "z" * 50),
            _chunk("FINAL_ANSWER_STARTReady."),
        ],
    )

    assert _parse_sse(response.text)[-1][1]["answer"] == "Ready."


def test_stream_reports_a_non_streaming_kickoff(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [],
        kickoff_return=object(),
    )

    events = _parse_sse(response.text)
    assert events[0][0] == "status"
    assert events[1][0] == "error"
    assert "Expected streaming output" in events[1][1]["message"]
    assert all(name != "done" for name, _data in events)


def test_stream_reports_a_kickoff_failure(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [],
        kickoff_error=RuntimeError("llm down"),
    )

    events = _parse_sse(response.text)
    assert events[0] == ("status", {"message": "started"})
    assert events[1] == ("error", {"message": "llm down"})


def test_stream_reports_a_history_save_failure(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_session.commit = AsyncMock(side_effect=RuntimeError("db down"))
    response, _crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [_chunk("FINAL_ANSWER_STARTSaved?")],
    )

    events = _parse_sse(response.text)
    assert events[-1] == ("error", {"message": "db down"})


def test_stream_returns_404_before_opening_the_crew(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, crew, calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [],
        executes=[scalar_result(None)],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"
    assert calls == []
    crew.kickoff.assert_not_called()


def test_stream_returns_400_when_a_document_is_not_ready(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, crew, _calls = _stream(
        auth_client,
        mock_session,
        monkeypatch,
        [],
        executes=[
            scalar_result(make_collection()),
            rows_result([make_document(status=DocumentStatus.FAILED, filename="broken.pdf")]),
        ],
    )

    assert response.status_code == 400
    assert "broken.pdf" in response.json()["detail"]
    crew.kickoff.assert_not_called()


def test_stream_requires_a_question(auth_client: TestClient) -> None:
    response = auth_client.post(f"/api/collections/{COLLECTION_ID}/query/stream", json={})

    assert response.status_code == 422
