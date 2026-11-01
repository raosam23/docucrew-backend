"""Non-streaming query and history routes. build_query_crew is replaced so kickoff never calls a model."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models.document import DocumentStatus
from app.schemas.query import Citations, QueryAnswer
from tests.factories import COLLECTION_ID, make_collection, make_document, make_history, rows_result, scalar_result


def _install_crew(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, list[bool]]:
    crew = MagicMock()
    task = MagicMock()
    task.output = None
    calls: list[bool] = []

    def _build(stream: bool = False) -> tuple[MagicMock, MagicMock]:
        calls.append(stream)
        return crew, task

    monkeypatch.setattr("app.api.routes.query.build_query_crew", _build)
    return crew, task, calls


def _ready(mock_session: AsyncMock, history: list[object] | None = None) -> None:
    mock_session.execute = AsyncMock(
        side_effect=[
            scalar_result(make_collection()),
            rows_result([make_document(status=DocumentStatus.READY)]),
            rows_result([] if history is None else history),
        ]
    )


def test_query_returns_the_structured_answer(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    earlier = make_history(question="What is PTO?", answer="Ten days.")
    _ready(mock_session, [earlier])
    crew, task, calls = _install_crew(monkeypatch)
    task.output = SimpleNamespace(
        pydantic=QueryAnswer(
            answer="Remote work is allowed on Fridays.",
            citations=[Citations(filename="policy.pdf", chunk_index=1, relevance_score=0.91)],
        )
    )

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Can I work remotely?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Remote work is allowed on Fridays."
    assert body["citations"] == [{"filename": "policy.pdf", "chunk_index": 1, "relevance_score": 0.91}]
    assert body["query_id"]
    assert calls == [False]
    inputs = crew.kickoff.call_args.kwargs["inputs"]
    assert inputs["question"] == "Can I work remotely?"
    assert inputs["collection_id"] == f"col_{COLLECTION_ID}"
    assert "What is PTO?" in inputs["chat_history"]
    assert "Ten days." in inputs["chat_history"]
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


def test_query_allows_a_collection_with_no_documents(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_session.execute = AsyncMock(
        side_effect=[
            scalar_result(make_collection()),
            rows_result([]),
            rows_result([]),
        ]
    )
    _crew, task, _calls = _install_crew(monkeypatch)
    task.output = SimpleNamespace(pydantic=QueryAnswer(answer="Nothing is uploaded.", citations=[]))

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Anything?"},
    )

    assert response.status_code == 200
    assert response.json()["citations"] == []


@pytest.mark.parametrize("status", [DocumentStatus.PENDING, DocumentStatus.PROCESSING, DocumentStatus.FAILED])
def test_query_rejects_documents_that_are_not_ready(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    status: DocumentStatus,
) -> None:
    mock_session.execute = AsyncMock(
        side_effect=[
            scalar_result(make_collection()),
            rows_result([make_document(status=status, filename="draft.pdf")]),
        ]
    )
    crew, _task, _calls = _install_crew(monkeypatch)

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Ready?"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == f"Document 'draft.pdf' is not ready (status: {status})"
    crew.kickoff.assert_not_called()


def test_query_returns_404_when_the_collection_is_missing(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Hello?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collections not found"


def test_query_returns_500_when_the_synthesizer_has_no_output(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ready(mock_session)
    _crew, task, _calls = _install_crew(monkeypatch)
    task.output = None

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Hello?"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to synthesize answer"


def test_query_returns_500_when_structured_output_is_missing(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ready(mock_session)
    _crew, task, _calls = _install_crew(monkeypatch)
    task.output = SimpleNamespace(pydantic=None)

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/query",
        json={"question": "Hello?"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to synthesize answer"


def test_query_requires_a_question(auth_client: TestClient) -> None:
    assert auth_client.post(f"/api/collections/{COLLECTION_ID}/query", json={}).status_code == 422


def test_history_returns_saved_queries(auth_client: TestClient, mock_session: AsyncMock) -> None:
    history = make_history()
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), rows_result([history])])

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}/history")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["question"] == history.question
    assert body[0]["answer"] == history.answer
    assert body[0]["citations"][0]["filename"] == "policy.pdf"
    assert body[0]["created_at"]


def test_history_can_be_empty(auth_client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), rows_result([])])

    assert auth_client.get(f"/api/collections/{COLLECTION_ID}/history").json() == []


def test_history_returns_404_when_the_collection_is_missing(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}/history")

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"
