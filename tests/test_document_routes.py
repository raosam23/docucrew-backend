"""Document upload, list, and delete. The ingestion crew and Chroma are mocked."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.routes.documents import upload_documents
from app.models.document import DocumentStatus, FileType
from tests.factories import (
    COLLECTION_ID,
    DOCUMENT_ID,
    make_collection,
    make_document,
    make_user,
    rows_result,
    scalar_result,
)


def _patch_crew(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    crew = MagicMock()
    monkeypatch.setattr("app.api.routes.documents.ingestion_crew", crew)
    return crew


def test_upload_runs_the_ingestion_crew_and_marks_documents_ready(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    collection = make_collection()
    mock_session.execute = AsyncMock(return_value=scalar_result(collection))
    crew = _patch_crew(monkeypatch)

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/documents/",
        files=[
            ("files", ("notes.txt", b"hello", "text/plain")),
            ("files", ("readme.md", b"# hi", "text/markdown")),
            ("files", ("scan.pdf", b"%PDF", "application/pdf")),
            ("files", ("brief.docx", b"PK", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["filename"] for item in body] == ["notes.txt", "readme.md", "scan.pdf", "brief.docx"]
    assert {item["status"] for item in body} == {"ready"}
    assert {item["file_type"] for item in body} == {"txt", "md", "pdf", "docx"}
    assert all(item["error_message"] is None for item in body)
    assert all(item["chunk_count"] is None for item in body)

    inputs = crew.kickoff.call_args.kwargs["inputs"]
    assert inputs["collection_id"] == collection.chroma_collection_id
    assert [item["file_path"] for item in inputs["files"]] == [
        f"./uploads/{COLLECTION_ID}/notes.txt",
        f"./uploads/{COLLECTION_ID}/readme.md",
        f"./uploads/{COLLECTION_ID}/scan.pdf",
        f"./uploads/{COLLECTION_ID}/brief.docx",
    ]
    assert {item["doc_id"] for item in inputs["files"]} == {item["id"] for item in body}
    assert (workdir / "uploads" / str(COLLECTION_ID) / "notes.txt").read_bytes() == b"hello"


def test_upload_accepts_an_uppercase_extension(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_collection()))
    _patch_crew(monkeypatch)

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/documents/",
        files=[("files", ("Notes.TXT", b"hi", "text/plain"))],
    )

    assert response.status_code == 200
    assert response.json()[0]["file_type"] == "txt"
    assert (workdir / "uploads" / str(COLLECTION_ID) / "Notes.TXT").is_file()


def test_upload_marks_documents_failed_when_ingestion_raises(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_collection()))
    crew = _patch_crew(monkeypatch)
    crew.kickoff.side_effect = RuntimeError("embed failed")

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/documents/",
        files=[
            ("files", ("a.txt", b"one", "text/plain")),
            ("files", ("b.txt", b"two", "text/plain")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["status"] for item in body] == ["failed", "failed"]
    assert all("embed failed" in item["error_message"] for item in body)


def test_upload_returns_404_when_the_collection_is_missing(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))
    crew = _patch_crew(monkeypatch)

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/documents/",
        files=[("files", ("a.txt", b"hi", "text/plain"))],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"
    crew.kickoff.assert_not_called()


def test_upload_rejects_an_unsupported_type(
    auth_client: TestClient,
    mock_session: AsyncMock,
    workdir: Path,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_collection()))

    response = auth_client.post(
        f"/api/collections/{COLLECTION_ID}/documents/",
        files=[("files", ("sheet.csv", b"a,b", "text/csv"))],
    )

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_files_over_10mb(mock_session: AsyncMock, workdir: Path) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(make_collection()))
    upload = UploadFile(file=io.BytesIO(b"x"), filename="big.txt", size=10 * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as exc:
        await upload_documents(COLLECTION_ID, [upload], make_user(), mock_session)

    assert exc.value.status_code == 400
    assert "too large" in exc.value.detail


def test_list_documents(auth_client: TestClient, mock_session: AsyncMock) -> None:
    document = make_document(file_type=FileType.TXT, filename="notes.txt")
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), rows_result([document])])

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}/documents")

    assert response.status_code == 200
    assert response.json()[0]["filename"] == "notes.txt"
    assert response.json()[0]["status"] == "ready"


def test_list_documents_can_be_empty(auth_client: TestClient, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), rows_result([])])

    assert auth_client.get(f"/api/collections/{COLLECTION_ID}/documents").json() == []


def test_list_documents_returns_404_for_an_unknown_collection(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = auth_client.get(f"/api/collections/{COLLECTION_ID}/documents")

    assert response.status_code == 404


def test_delete_document_removes_the_file_and_chroma_chunks(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    collection = make_collection()
    document = make_document()
    path = workdir / "uploads" / str(COLLECTION_ID) / document.filename
    path.parent.mkdir(parents=True)
    path.write_text("stored", encoding="utf-8")
    mock_session.execute = AsyncMock(side_effect=[scalar_result(collection), scalar_result(document)])
    deleted = MagicMock()
    monkeypatch.setattr("app.api.routes.documents.delete_chunks_by_doc_id", deleted)

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}")

    assert response.status_code == 204
    assert not path.exists()
    deleted.assert_called_once_with(collection.chroma_collection_id, str(document.id))
    mock_session.delete.assert_awaited_once()


def test_delete_document_succeeds_when_the_file_is_already_gone(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), scalar_result(make_document())])
    deleted = MagicMock()
    monkeypatch.setattr("app.api.routes.documents.delete_chunks_by_doc_id", deleted)

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}")

    assert response.status_code == 204
    deleted.assert_called_once()


def test_delete_document_is_blocked_while_processing(
    auth_client: TestClient,
    mock_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    workdir: Path,
) -> None:
    document = make_document(status=DocumentStatus.PROCESSING)
    path = workdir / "uploads" / str(COLLECTION_ID) / document.filename
    path.parent.mkdir(parents=True)
    path.write_text("working", encoding="utf-8")
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), scalar_result(document)])
    deleted = MagicMock()
    monkeypatch.setattr("app.api.routes.documents.delete_chunks_by_doc_id", deleted)

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}")

    assert response.status_code == 400
    assert response.json()["detail"] == "Document is being processed"
    assert path.is_file()
    deleted.assert_not_called()
    mock_session.delete.assert_not_called()


def test_delete_document_returns_404_for_a_missing_collection(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.execute = AsyncMock(return_value=scalar_result(None))

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection not found"


def test_delete_document_returns_404_for_a_missing_document(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.execute = AsyncMock(side_effect=[scalar_result(make_collection()), scalar_result(None)])

    response = auth_client.delete(f"/api/collections/{COLLECTION_ID}/documents/{DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
