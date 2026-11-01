"""ChromaDB ingestion and retrieval. The client is a double, so no embedding model is downloaded."""

from unittest.mock import MagicMock

import pytest

import app.services.collection_service as collection_service
from app.services.chroma_service import (
    add_chunks,
    delete_chunks_by_doc_id,
    delete_collection,
    get_or_create_collection,
    search,
)


@pytest.fixture
def chroma(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    collection = MagicMock()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    monkeypatch.setattr("app.services.chroma_service.chroma_client", client)
    return client, collection


def test_collection_service_module_imports() -> None:
    assert collection_service.__name__ == "app.services.collection_service"


def test_get_or_create_collection_uses_cosine_space(chroma: tuple[MagicMock, MagicMock]) -> None:
    client, collection = chroma

    assert get_or_create_collection("col_1") is collection
    client.get_or_create_collection.assert_called_once_with(
        name="col_1",
        metadata={"hnsw:space": "cosine"},
    )


def test_add_chunks_stores_text_metadata_and_ids(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma
    chunks = [
        {"text": "alpha", "metadata": {"doc_id": "doc-1", "chunk_index": 0}},
        {"text": "beta", "metadata": {"doc_id": "doc-1", "chunk_index": 1}},
    ]

    add_chunks("col_1", chunks)

    collection.add.assert_called_once_with(
        documents=["alpha", "beta"],
        metadatas=[chunks[0]["metadata"], chunks[1]["metadata"]],
        ids=["doc-1_0", "doc-1_1"],
    )


def test_search_maps_hits_and_honours_top_k(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma
    collection.query.return_value = {
        "documents": [["alpha", "beta"]],
        "metadatas": [[{"doc_id": "doc-1"}, {"doc_id": "doc-2"}]],
        "distances": [[0.1, 0.4]],
    }

    hits = search("col_1", "remote work", top_k=2)

    collection.query.assert_called_once_with(query_texts=["remote work"], n_results=2)
    assert hits == [
        {"text": "alpha", "metadata": {"doc_id": "doc-1"}, "distance": 0.1},
        {"text": "beta", "metadata": {"doc_id": "doc-2"}, "distance": 0.4},
    ]


def test_search_returns_empty_when_there_are_no_documents(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma
    collection.query.return_value = {"documents": None, "metadatas": None, "distances": None}

    assert search("col_1", "anything") == []
    collection.query.assert_called_once_with(query_texts=["anything"], n_results=8)


def test_search_allows_missing_metadata_and_distances(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma
    collection.query.return_value = {
        "documents": [["only text"]],
        "metadatas": None,
        "distances": None,
    }

    assert search("col_1", "q") == [{"text": "only text", "metadata": None, "distance": None}]


def test_search_ignores_an_empty_hit_list(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma
    collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    assert search("col_1", "q") == []


def test_delete_collection_swallows_client_errors(chroma: tuple[MagicMock, MagicMock]) -> None:
    client, _collection = chroma
    delete_collection("col_1")
    client.delete_collection.assert_called_once_with("col_1")

    client.delete_collection.side_effect = Exception("already gone")
    delete_collection("col_1")


def test_delete_chunks_by_doc_id(chroma: tuple[MagicMock, MagicMock]) -> None:
    _client, collection = chroma

    delete_chunks_by_doc_id("col_1", "doc-1")

    collection.delete.assert_called_once_with(where={"doc_id": "doc-1"})
