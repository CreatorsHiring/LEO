# LEO: Local On-Premise AI Workbench

**Self-hosted, air-gapped AI workbench for open-weight models.** All data, prompts, embeddings, and responses remain on your infrastructure. No cloud dependencies.

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Prerequisites](#prerequisites)
5. [Installation & Getting Started](#installation--getting-started)
6. [Configuration](#configuration)
7. [API Endpoints](#api-endpoints)
8. [Development](#development)
9. [Roadmap](#roadmap)

---

## Overview

LEO is a self-hosted AI workbench designed for organizations requiring air-gapped, local-only AI capabilities. It integrates document ingestion, retrieval-augmented generation (RAG), and domain-specialized model routing — all running locally with open-weight models via Ollama and Qdrant.

**Core Philosophy:**
- **Air-gapped by design** — no data leaves your infrastructure
- **Domain-routed** — queries are automatically dispatched to specialized expert models
- **Citation-aware** — responses include source attribution from retrieved documents
- **Extension-friendly** — add models and providers without API changes

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Chat Interface** | Modern UI with streaming SSE responses, domain pills, and citation chips |
| **Document Ingestion** | PDF, DOCX, TXT, MD, CSV upload with automatic text extraction |
| **RAG Pipeline** | Local embedding (Ollama `nomic-embed-text` or SentenceTransformer) + Qdrant vector store |
| **Domain Routing** | Automatic prompt routing to specialized models (general, code, math, medical) |
| **Streaming** | Server-Sent Events for token-by-token response display |
| **Model Registry** | Centralized model configuration with domain-to-model mappings |
| **Upload Limits** | Configurable max upload size (default: 50 MB) |
| **Health Checks** | Built-in `/api/health` endpoint for monitoring |

---

## Architecture

### High-Level Flow

```
User Interface (index.html)
       ↓
FastAPI Backend (backend/app/main.py)
       ↓
1. Router: Prompt → Ollama router model → JSON {domain, confidence, rationale, needs_retrieval}
       ↓
2. Validator: Heuristic signal detection (code/math/medical keyword correction)
       ↓
3. Model Selection: Domain → ModelConfig from registry (specialized model + system prompt)
       ↓
4. Retrieval (if needed): Embed query → Qdrant similarity search → Retrieved chunks
       ↓
5. Generation: Build prompt + stream from expert model
       ↓
6. SSE Streaming: route → retrieval → model → token → warning/error → done events
```

### Domain Model Registry

| Domain | Model | Temperature | System Prompt Focus |
|--------|-------|-------------|---------------------|
| `general` | `qwen2.5:3b-instruct` | 0.3 | General-purpose, cite sources |
| `code` | `qwen2.5-coder:3b-instruct` | 0.15 | Coding expert, secure code, tradeoffs |
| `math` | `qwen2.5-math:1.5b-instruct` | 0.1 | Math expert, show steps, flag assumptions |
| `medical` | `qwen2.5:3b-instruct` | 0.1 | Cautious medical info, cite documents, recommend clinical judgment |

### RAG Pipeline

```
Upload (PDF/DOCX/TXT/MD/CSV)
     ↓
extract_text() → per-page/DOCX-section breakdown
     ↓
chunk_records() → overlapping chunks (chunk_size=1000, chunk_overlap=180)
     ↓
_embed_texts() → Ollama embeddings (nomic-embed-text) or SentenceTransformer
     ↓
Qdrant upsert → vectors + metadata (filename, page, section, chunk)
     ↓
search() → similarity search with optional document_id filter
     ↓
_format_context() → citation-formatted context text
```

### Services Dependencies

```
index.html (UI)
    ↓
FastAPI + Uvicorn (backend)
    ↓
Ollama API (models + embeddings)
    ↓
Qdrant API (vector storage)
    ↓
Local file system (uploads, data)
```

---

## Prerequisites

### Software

| Requirement | Version/Notes |
|-------------|---------------|
| **Docker** | For Qdrant vector database |
| **Python** | 3.12+ |
| **Ollama** | Latest version with required models pulled |
| **Git** | For repository management |

### Hardware

- GPU recommended for model inference (Ollama will use CPU if no GPU available)
- Minimum 8 GB RAM for small models (1.5B), 16+ GB for 3B/7B models
- Storage: 5 GB+ for models, embeddings, and document index

### Ollama Models (required)

Pull all required models via Ollama:

```bash
ollama pull qwen2.5:1.5b-instruct    # router
ollama pull qwen2.5:3b-instruct     # general/medical
ollama pull qwen2.5-coder:3b-instruct # code
ollama pull qwen2.5-math:1.5b-instruct # math
ollama pull nomic-embed-text          # default embedding model
```

---

## Installation & Getting Started

### 1. Start Qdrant Service

```powershell
# From the project root
docker compose up -d
```

Qdrant will be available at `http://localhost:6333`.

### 2. Set Up Python Environment

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```powershell
# Copy example environment file
copy .env.example .env

# Edit .env with your configuration
# - LEO_OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
# - LEO_ROUTER_MODEL: Default router model
# - LEO_EMBEDDING_PROVIDER: ollama or sentence-transformers
# - LEO_DEFAULT_EMBEDDING_MODEL: Embedding model name
# - LEO_QDRANT_URL: Qdrant server URL
# - LEO_QDRANT_COLLECTION: Vector collection name
```

### 4. Run the Application

```powershell
# Start the FastAPI backend
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 5. Open the UI

Navigate to: **http://127.0.0.1:8000**

The interface will auto-load and connect to the backend API.

---

## Configuration

Copy `.env.example` to `.env` and modify as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `LEO_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `LEO_ROUTER_MODEL` | `qwen2.5:1.5b-instruct` | Default router model name |
| `LEO_EMBEDDING_PROVIDER` | `ollama` | Embedding provider: `ollama` or `sentence-transformers` |
| `LEO_DEFAULT_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `LEO_QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `LEO_QDRANT_COLLECTION` | `leo_docs` | Vector collection name |
| `LEO_MAX_UPLOAD_MB` | `50` | Maximum upload size in MB |
| `LEO_CHUNK_SIZE` | `1000` | RAG chunk size in characters |
| `LEO_CHUNK_OVERLAP` | `180` | RAG chunk overlap in characters |
| `LEO_RETRIEVAL_TOP_K` | `5` | Number of retrieved chunks per query |

### Model Registry

Update the model registry in `backend/app/llm/registry.py` to add new domains/models:

```python
from typing import Dict
from dataclasses import dataclass

@dataclass
class ModelConfig:
    name: str
    temperature: float
    system_prompt: str

MODEL_REGISTRY: Dict[str, ModelConfig] = {
    "general": ModelConfig(
        name="qwen2.5:3b-instruct",
        temperature=0.3,
        system_prompt="You are a general-purpose AI assistant. Answer the user's query using the provided context when applicable. Cite your sources using [filename p.page chunk_id] notation."
    ),
    # Add new domains here...
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | `GET` | Serves the local UI (index.html) |
| `/api/health` | `GET` | Health check - verifies backend, Ollama, and Qdrant connectivity |
| `/api/chat/stream` | `POST` | Stream chat response with domain routing and optional RAG |
| `/api/documents` | `POST` | Upload a document for RAG ingestion |
| `/api/documents` | `GET` | List uploaded documents |
| `/api/documents/{doc_id}` | `DELETE` | Remove a document and its vectors |

### Request/Response Models

**Chat Request:**
```json
{
    "message": "string",
    "conversation_id": "string (optional)",
    "session_id": "string (optional)"
}
```

**Chat Stream SSE Events:**
- `route` — domain routing decision
- `retrieval` — query embedding and search results
- `token` — individual generated tokens
- `done` — completion summary
- `error` — error information

**Document Upload:**
- `multipart/form-data` with `file` field
- Supports: PDF, DOCX, TXT, MD, CSV
- Max size: 50 MB (configurable)

---

## Development

### Project Structure

```
LEO/
├── .env.example          # Environment configuration template
├── ARCHITECTURE.md       # Detailed architecture document
├── codeflow.md           # Code flow overview
├── data/                 # Uploaded documents directory
├── docker-compose.yml    # Qdrant service orchestration
├── index.html            # Local browser UI (SPA)
├── requirements.txt      # Python dependencies
├── roadmap.md            # Feature roadmap
└── backend/              # FastAPI application
    ├── app/
    │   ├── config.py      # Pydantic settings (LEO_ prefix)
    │   ├── main.py        # FastAPI entry point
    │   ├── router.py      # Prompt router using Ollama
    │   ├── route_validator.py # Route validation with signal detection
    │   ├── models.py      # Pydantic data models
    │   ├── llm/
    │   │   ├── __init__.py
    │   │   ├── ollama.py  # Ollama client adapter
    │   │   └── registry.py # Domain-to-model registry
    │   └── rag/
    │       ├── __init__.py
    │       ├── extractors.py  # PDF/DOCX/TXT/MD/CSV extraction
    │       ├── chunking.py    # Overlapping text chunking
    │       └── store.py       # Qdrant vector storage & retrieval
    └── __pycache__/
```

### Running Tests

```powershell
# From the project root
pytest tests/ -v
```

### Code Style

- Python 3.12+ compatible
- Pydantic v2 for data modeling
- Black/formatted code (check existing style)
- Type hints throughout

### Adding New Features

1. **New domain/model**: Update `MODEL_REGISTRY` in `backend/app/llm/registry.py`
2. **New document format**: Add extractor in `backend/app/rag/extractors.py`
3. **New embedding provider**: Modify `backend/app/rag/store.py` and update config
4. **API endpoint**: Add route in `backend/app/router.py` and handler in `backend/app/main.py`

---

## Roadmap

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1** | ✅ Complete | Router, expert selection, streaming |
| **Phase 2** | ⬜ Upcoming | RAG pipeline, PDF upload, document retrieval |
| **Phase 3** | ⬜ Planned | Source citations, router evaluation |
| **Phase 4** | ⬜ Planned | Offline verification, enhanced UI |

---

## Air-Gap Considerations

### Pre-Depployment Checklist

- [ ] Mirror all Python wheels into the offline environment
- [ ] Pull all required Ollama models locally
- [ ] Build and push Docker images if using custom registries
- [ ] Verify Qdrant data directory is persisted locally
- [ ] Confirm no CDN or external API dependencies in the UI
- [ ] Test full workflow offline (no network access)

### Configuration for Air-Gapped Environments

- Set `LEO_OLLAMA_BASE_URL` to local Ollama instance address
- Set `LEO_QDRANT_URL` to local Qdrant instance address
- Ensure `LEO_EMBEDDING_PROVIDER=ollama` uses locally-available models
- If using `sentence-transformers`, mirror the model weights locally

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Ollama** for local model serving
- **Qdrant** for vector storage
- **pdfplumber** and **python-docx** for document extraction
- **FastAPI** for the web framework