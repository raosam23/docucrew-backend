"""Local document parsing. PDF and DOCX libraries are exercised in-process, with no network."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docx import Document as DocxDocument

from app.services.file_service import parse_file


def test_parse_txt_and_markdown(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("plain text", encoding="utf-8")
    markdown_path = tmp_path / "notes.md"
    markdown_path.write_text("# Title\n", encoding="utf-8")
    empty_path = tmp_path / "empty.txt"
    empty_path.write_text("", encoding="utf-8")

    assert parse_file(str(text_path)) == "plain text"
    assert parse_file(str(markdown_path)) == "# Title\n"
    assert parse_file(str(empty_path)) == ""


def test_parse_docx_concatenates_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "brief.docx"
    document = DocxDocument()
    document.add_paragraph("Hello")
    document.add_paragraph("World")
    document.save(path)

    empty = tmp_path / "empty.docx"
    DocxDocument().save(empty)

    assert parse_file(str(path)) == "HelloWorld"
    assert parse_file(str(empty)) == ""


def test_parse_pdf_joins_page_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4")
    seen: dict[str, str] = {}

    def _reader(file_path: str) -> MagicMock:
        seen["path"] = file_path
        first = MagicMock()
        first.extract_text.return_value = "Hello"
        second = MagicMock()
        second.extract_text.return_value = "World"
        reader = MagicMock()
        reader.pages = [first, second]
        return reader

    monkeypatch.setattr("app.services.file_service.PdfReader", _reader)

    assert parse_file(str(path)) == "HelloWorld"
    assert seen["path"] == str(path)


def test_parse_file_rejects_unknown_types(tmp_path: Path) -> None:
    path = tmp_path / "sheet.csv"
    path.write_text("a,b", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_file(str(path))
