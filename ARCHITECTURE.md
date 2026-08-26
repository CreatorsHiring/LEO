# LEO Phase 1 Architecture

LEO is a self-hosted, air-gapped AI workbench. The Phase 1 website provides chat, local document ingestion, RAG, model routing, and streamed responses without sending organization data to cloud models.

## Goals

- Keep all prompts, uploads, embeddings, vectors, and generated output on the organization's own machine or GPU server.
- Route every user prompt through a small local orchestrator model before selecting an expert model.
- Support multiple open-weight models at once and allow new models to be registered without redesigning the backend.
- Provide document-grounded answers with citations for local PDFs, DOCX files, and text files.
- Stream answers to the browser so the UX feels like a real workbench, not a blocking form.

## Runtime Components

- `index.html`: Local browser UI for chat, document upload, routing status, selected model display, and citation chips.
- `backend/app/main.py`: FastAPI entry point. Serves the UI and exposes health, upload, and streaming chat endpoints.
- `backend/app/router.py`: Prompt router. Uses `Qwen2.5-1.5B` via Ollama-compatible local chat and requires structured JSON.
- `backend/app/llm/registry.py`: Domain-to-model registry. This is the extension point for adding or swapping expert models.
- `backend/app/llm/ollama.py`: Local model-server adapter. The backend is isolated from Ollama details behind this class.
- `backend/app/rag/extractors.py`: Local text extraction for PDF, DOCX, TXT, MD, and CSV.
- `backend/app/rag/chunking.py`: Overlapping chunk creation.
- `backend/app/rag/store.py`: Local embeddings and Qdrant vector storage. Ollama embeddings are the default; SentenceTransformers can be enabled when pre-staged locally.
- `docker-compose.yml`: Local Qdrant service.

## Chat Flow

1. User sends a prompt from the website.
2. Backend asks the router model for strict JSON:

   ```json
   {
     "domain": "general",
     "confidence": 0.85,
     "rationale": "Short reason",
     "needs_retrieval": true
   }
   ```

3. The router never answers the user directly.
4. Backend maps `domain` to a registered expert model.
5. If documents are attached or retrieval is requested, backend embeds the query and retrieves top-k chunks from Qdrant.
6. Backend constructs a prompt containing system instructions, recent chat history, retrieved context, and the user request.
7. Selected expert model generates the answer through the local model server.
8. Backend streams Server-Sent Events to the browser:

   - `route`
   - `retrieval`
   - `model`
   - `token`
   - `warning`
   - `error`
   - `done`

## Domain Model Registry

The current domains are:

- `general`: `qwen2.5:3b-instruct`
- `code`: `qwen2.5-coder:3b-instruct`
- `math`: `qwen2.5-math:1.5b-instruct`
- `medical`: `qwen2.5:3b-instruct`

To add a model, update `MODEL_REGISTRY` in `backend/app/llm/registry.py`. The API does not need to change as long as the new model is reachable through the configured local model adapter.

## RAG Pipeline

1. Upload endpoint accepts PDF, DOCX, TXT, MD, and CSV.
2. Files are written to `data/uploads`.
3. Text extraction happens locally.
4. Text is normalized and chunked with overlap.
5. Chunks are embedded using the configured local embedding model.
6. Vectors and metadata are stored in local Qdrant.
7. Retrieval returns chunk text plus metadata:

   - `document_id`
   - `filename`
   - `page`
   - `section`
   - `chunk`

8. Responses are instructed to cite retrieved context as `[filename p.page chunk id]`.

## Local Services

Start Qdrant:

```powershell
docker compose up -d
```

Install Python dependencies in a local environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Pull or register local Ollama models:

```powershell
ollama pull qwen2.5:1.5b-instruct
ollama pull qwen2.5:3b-instruct
ollama pull qwen2.5-coder:3b-instruct
ollama pull qwen2.5-math:1.5b-instruct
```

Run the API and website:

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Air-Gap Notes

- The UI has no CDN dependencies.
- The backend points to local Ollama and local Qdrant by default.
- Ollama embeddings are used by default with `nomic-embed-text`. Pull or mirror that embedding model before air-gapped use.
- `sentence-transformers` can be used by setting `LEO_EMBEDDING_PROVIDER=sentence-transformers`, but install the package and pre-stage the model locally first.
- Python wheels, Docker images, Ollama models, and embedding models must be mirrored into the environment before disconnecting from the network.

## Phase 1 Limitations

- OCR, handwriting recognition, engineering drawing analysis, and photograph understanding are planned but not implemented in this slice.
- Chat history is browser-memory only.
- There is no authentication or tenant isolation yet.
- The model adapter currently targets Ollama-compatible local serving. Additional adapters can be added behind the same `OllamaClient` usage pattern or by introducing a `ModelClient` interface.
