from pathlib import Path
import json
from urllib import request
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchAny, PointStruct, VectorParams

from backend.app.config import get_settings
from backend.app.models import RetrievedChunk, UploadedDocument
from backend.app.rag.chunking import chunk_records
from backend.app.rag.extractors import extract_text


class DocumentStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = QdrantClient(url=self.settings.qdrant_url)
        self._sentence_encoder = None

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        if any(collection.name == self.settings.qdrant_collection for collection in collections):
            return
        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def ingest(self, path: Path, original_filename: str) -> UploadedDocument:
        document_id = str(uuid4())
        records = extract_text(path)
        chunks = chunk_records(records)
        if not chunks:
            return UploadedDocument(document_id=document_id, filename=original_filename, chunks_indexed=0)

        vectors = self._embed_texts([chunk["text"] for chunk in chunks])
        self._ensure_collection(len(vectors[0]))

        points = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
            points.append(
                PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload={
                        "document_id": document_id,
                        "filename": original_filename,
                        "page": chunk.get("page"),
                        "section": chunk.get("section"),
                        "chunk": index,
                        "text": chunk["text"],
                    },
                )
            )

        if points:
            self.client.upsert(collection_name=self.settings.qdrant_collection, points=points)

        return UploadedDocument(document_id=document_id, filename=original_filename, chunks_indexed=len(points))

    def search(self, query: str, document_ids: list[str], top_k: int | None = None) -> list[RetrievedChunk]:
        vector = self._embed_texts([query])[0]
        self._ensure_collection(len(vector))
        query_filter = None
        if document_ids:
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchAny(any=document_ids))]
            )

        results = self.client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k or self.settings.retrieval_top_k,
        )
        return [
            RetrievedChunk(
                text=result.payload.get("text", ""),
                score=float(result.score),
                metadata={key: value for key, value in result.payload.items() if key != "text"},
            )
            for result in results
        ]

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.settings.embedding_provider == "sentence-transformers":
            return self._embed_with_sentence_transformers(texts)
        return self._embed_with_ollama(texts)

    def _embed_with_ollama(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            req = request.Request(
                f"{self.settings.ollama_base_url}/api/embeddings",
                data=json.dumps({"model": self.settings.default_embedding_model, "prompt": text}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=None) as response:
                vectors.append(json.loads(response.read().decode("utf-8"))["embedding"])
        return vectors

    def _embed_with_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        if self._sentence_encoder is None:
            from sentence_transformers import SentenceTransformer

            self._sentence_encoder = SentenceTransformer(self.settings.default_embedding_model)
        vectors = self._sentence_encoder.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]
