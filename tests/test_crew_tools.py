"""CrewAI tools delegate to the file parser and the Chroma service. Those calls are mocked."""

import pytest

from app.crews.tools import (
    ChromaSearchTool,
    ChromaSearchToolArgs,
    ChromaStoreTool,
    ChromaStoreToolArgs,
    FileReaderTool,
)


def test_file_reader_tool_returns_parsed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.crews.tools.parse_file", lambda path: f"parsed:{path}")

    assert FileReaderTool()._run("/tmp/notes.txt") == "parsed:/tmp/notes.txt"


def test_file_reader_tool_propagates_parser_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_path: str) -> str:
        raise ValueError("Unsupported file type: /tmp/sheet.csv")

    monkeypatch.setattr("app.crews.tools.parse_file", _boom)

    with pytest.raises(ValueError, match="Unsupported file type"):
        FileReaderTool()._run("/tmp/sheet.csv")


def test_chroma_store_tool_passes_chunks_through(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _add(collection_id: str, chunks: list[dict[str, object]]) -> None:
        seen["collection_id"] = collection_id
        seen["chunks"] = chunks

    monkeypatch.setattr("app.crews.tools.add_chunks", _add)
    chunks = [{"text": "clause 4", "metadata": {"doc_id": "d1", "chunk_index": 0}}]

    assert ChromaStoreTool()._run("col_1", chunks) is None
    assert seen == {"collection_id": "col_1", "chunks": chunks}
    assert ChromaStoreToolArgs(collection_id="col_1", chunks=chunks).collection_id == "col_1"


def test_chroma_search_tool_defaults_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    def _search(collection_id: str, query: str, top_k: int = 8) -> list[dict[str, object]]:
        return [{"collection_id": collection_id, "query": query, "top_k": top_k}]

    monkeypatch.setattr("app.crews.tools.search", _search)

    assert ChromaSearchTool()._run("col_1", "refunds") == [{"collection_id": "col_1", "query": "refunds", "top_k": 8}]
    assert ChromaSearchTool()._run("col_1", "refunds", top_k=3)[0]["top_k"] == 3
    assert ChromaSearchToolArgs(collection_id="col_1", query="refunds").top_k == 8
