from pathlib import Path
import docx
import pdfplumber


def extract_text(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix in {".txt", ".md", ".csv"}:
        return [{"text": path.read_text(encoding="utf-8", errors="ignore"), "page": None, "section": None}]
    raise ValueError(f"Unsupported file type: {suffix}")


def _extract_pdf(path: Path) -> list[dict]:
    pages: list[dict] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"text": text, "page": index, "section": None})
    return pages


def _extract_docx(path: Path) -> list[dict]:
    document = docx.Document(path)
    sections: list[dict] = []
    current_heading = None
    buffer: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style and paragraph.style.name.lower().startswith("heading"):
            if buffer:
                sections.append({"text": "\n".join(buffer), "page": None, "section": current_heading})
                buffer = []
            current_heading = text
        else:
            buffer.append(text)

    if buffer:
        sections.append({"text": "\n".join(buffer), "page": None, "section": current_heading})

    return sections
