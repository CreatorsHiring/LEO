from collections.abc import Iterable
from backend.app.config import get_settings


def chunk_records(records: Iterable[dict]) -> list[dict]:
    settings = get_settings()
    chunks: list[dict] = []

    for record in records:
        text = " ".join(record["text"].split())
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + settings.chunk_size, len(text))
            chunk_text = text[start:end]
            chunks.append(
                {
                    "text": chunk_text,
                    "page": record.get("page"),
                    "section": record.get("section"),
                }
            )
            if end == len(text):
                break
            start = max(0, end - settings.chunk_overlap)

    return chunks
