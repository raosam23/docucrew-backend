from pypdf import PdfReader
from docx import Document as DocxDocument

def parse_file(file_path: str) -> str:
    """
    Parse a file and return the text content
    Args:
        file_path: The path to the file to parse
    Returns:
        The text content of the file
    Raises:
        ValueError: If the file type is not supported
    """
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    if file_path.endswith(".docx"):
        doc = DocxDocument(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text
        return text
    if file_path.endswith(".txt") or file_path.endswith(".md"):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    raise ValueError(f"Unsupported file type: {file_path}")
