# LEO — Complete Roadmap: Website, Desktop App, CLI Agent

## Where the repo actually stands today

From `README.md`, `ARCHITECTURE.md`, and `roadmap.md`:

- **Stack**: Python 3.12, FastAPI + Uvicorn backend, vanilla `index.html` frontend, Ollama for models, Qdrant (Docker) for vectors.
- **Working now**: router (`qwen2.5:1.5b-instruct` → strict JSON `{domain, confidence, rationale, needs_retrieval}`), domain→model registry (general/code/math/medical), SSE token streaming, health check.
- **Explicitly not built yet**: RAG (upload, chunking, retrieval, citations), OCR/handwriting/drawings/photos, chat history persistence, auth, and — going beyond what `roadmap.md` even lists — any agentic tool-calling, file read/write, code execution, spreadsheet work, or document generation (docx/pptx/xlsx). Those last ones are the bulk of what you're now asking for.
- **`medical` as a domain** still doesn't match your problem statement (approval notes, SOPs, drawings, inspection reports). Recommend dropping it or relabeling it something like `safety`/`compliance` if that's what it's standing in for — keeps the registry honest.

Everything below builds on this codebase rather than replacing it.

## Architectural decision: one core, three shells

Don't build three separate agent implementations. Build **one Python core** (`leo/core/`) containing the router, model registry, RAG store, tool-calling loop, and document generators. Then:

- **Website** = FastAPI HTTP/SSE wrapper around the core (what exists today, extended).
- **Desktop app** = Tauri or Electron shell that either (a) spawns the same FastAPI process locally and loads it in a webview, or (b) if you want a native feel, a PyQt/PySide app importing `leo/core/` directly. For a hackathon, (a) is far less work — you already have the web UI, you're just giving it filesystem access it doesn't have in a browser.
- **CLI agent** = a Typer/Click entry point (`leo agent ...`) that imports `leo/core/` directly — no HTTP hop, lowest latency, closest to a Claude Code-style tool.

This is the single highest-leverage decision for your timeline: every tool you build (file read/write, code exec, spreadsheet, RAG search, OCR, doc generation) gets written once in the core and is usable by all three surfaces.

---

## Shared core (`leo/core/`) — build this first

This is the part that makes "agentic" real. Everything else is UI around it.

### 1. Tool-calling / agent loop
**What**: A ReAct-style loop — model emits either a `tool_call` (JSON: `{"tool": "...", "args": {...}}`) or a `final_answer`. Backend executes the tool, appends the result to context, loops until final answer or a max-iteration cap (e.g. 8–12 steps).
**How**: Reuse the JSON-mode discipline already in `router.py` (`format: "json"` in the Ollama call) — don't regex-parse tool calls, force structured output the same way the router forces its routing JSON. Define a `Tool` interface (`name`, `description`, `args_schema`, `run()`), register tools in a dict, and give the model a compact list of tool names + one-line descriptions in the system prompt so it knows what's callable.
**Multi-step / "iterate, don't answer once"**: Before executing, have the model emit a short plan (numbered steps) as its first output; store it as task state; after each tool result, ask "is the task done, or is the next step X?" rather than looping blindly. Keep this simple for the hackathon — a plan list + step pointer, not a full recursive planner.

### 2. File read/write tool (sandboxed)
**What**: `read_file(path)`, `write_file(path, content)`, `list_dir(path)`, `search_files(pattern)`.
**How**: Restrict to a configured workspace root (e.g. `LEO_WORKSPACE_DIR`); resolve and validate every path stays inside it before touching disk — this is your sandbox boundary, not a container. For the CLI agent specifically, mirror Claude Code's permission model: destructive writes (overwrite, delete) require an explicit confirm flag or a dry-run diff shown first.

### 3. Code execution sandbox
**What**: Run generated code and return stdout/stderr/exit code.
**How (hackathon-scoped)**: `subprocess.run()` in a temp directory, with a hard timeout and resource limits (`resource.setrlimit` on Linux/Mac, or `subprocess` timeout on Windows), no network access from the subprocess environment. This is "sandboxed enough" for a demo. If you have time left, upgrade to a Docker container per execution for real isolation — don't start there.

### 4. Spreadsheet tool
**What**: `read_sheet(path)`, `write_sheet(path, data)`, `update_cells(path, changes)`, and a "monitor" mode.
**How**: `openpyxl` for read/write/formula access. "Monitor a spreadsheet" = a `watchdog`-based file watcher on a folder or specific file; on change, re-read it, run whatever check the task defined (e.g. flag out-of-range values, recompute a dependent summary), and surface that as a notification or a follow-up agent turn. This only makes sense in the desktop app and CLI agent (a browser can't watch the local filesystem) — the website can still do one-shot spreadsheet read/generate via upload/download.

### 5. Internal document search tool
**What**: `search_kb(query, top_k)` — same retrieval you're about to build for chat-time RAG, exposed as a callable tool so the agent can search mid-task, not just at the start of a conversation.
**How**: Thin wrapper around `backend/app/rag/store.py`'s `search()`. This is nearly free once RAG exists — just don't hardcode retrieval to only fire before generation; let the agent loop call it whenever it decides it needs grounding.

### 6. Document generation tools
**What**: `generate_docx(content, template?)`, `generate_pptx(slides)`, `generate_xlsx(sheets)`, plus a calculations-with-steps formatter for approval notes.
**How**: `python-docx`, `python-pptx`, `openpyxl` — all pure Python, no external service, fits your stack exactly. Keep each as a tool the agent can call with structured input (e.g. a list of slide objects, a list of {section, body} for docx) rather than free text, so output is reliably well-formed. Save to a `LEO_OUTPUT_DIR`, return a path/download link.

### 7. Vision / OCR pipeline
**What**: scanned PDFs, handwritten notes, engineering drawings, photographs → text/structured description.
**How (CPU, no GPU)**: Tier it rather than sending everything to a heavy vision model:
- **Printed text, clean scans**: Tesseract (`pytesseract`) — fast, CPU-only, already battle-tested for this.
- **Handwriting, drawings, photos, messy layouts**: a small open-weight VLM via Ollama. On CPU, favor the smallest capable option — `moondream` (~1.6B) or `llava-phi3` run noticeably better on CPU than a 7B+ Qwen-VL. Expect this tier to be slow; scope your demo inputs accordingly (a couple of representative handwritten/drawing samples, not a batch).
- Route between the two with a cheap heuristic first (e.g. Tesseract confidence score below a threshold → escalate to the VLM) rather than always paying the VLM cost.

### 8. Grounding / citations
Already scoped in your roadmap (Phase 2/3) — retrieved chunks carry `filename/page/section/chunk`, and the system prompt instructs `[filename p.page chunk_id]` citation format. Extend this so agent tool calls to `search_kb` also carry citations into generated deliverables (an approval note that cites the SOP paragraph it's based on is a strong demo moment).

---

## 1. Website

Everything below is additive to the existing FastAPI + `index.html` + SSE setup.

| Feature | Approach |
|---|---|
| Chat (exists) | Keep as-is |
| Streaming (exists) | Keep as-is |
| Router + expert selection (exists) | Keep as-is; consider dropping/relabeling `medical` |
| File upload (PDF, TXT, DOCX, MD, CSV — mostly exists per README) | Extend `extractors.py` to also handle image formats (PNG/JPG/scanned PDF pages) by routing them into the OCR/vision tier above instead of the text extractor |
| RAG pipeline (planned, not built) | Build per `ARCHITECTURE.md`'s existing design — chunk → embed → Qdrant upsert → retrieve → cite. This is your highest-priority remaining item; agent tool-calling and doc generation both depend on `search_kb` existing |
| Structured deliverables (code, Word, PPT, Excel) | Detect output-type intent either via an explicit UI toggle ("respond as: chat / Word / PPT / Excel") or let the router's JSON include a `deliverable_type` field alongside `domain`; call the matching generator tool and return a download link in the SSE `done` event |
| Calculations with steps shown | A response-formatting convention, not a new tool: system prompt instructs the model to emit a numbered `Given / Steps / Result` structure; render it distinctly in the UI (monospace block) so it doesn't look like ordinary chat |
| Source citations (planned) | Render as clickable chips per `ARCHITECTURE.md`'s plan; clicking opens the source doc at the cited page |
| Document library view | New endpoint listing ingested docs (already have `GET/DELETE /api/documents`) — just needs a UI panel |
| Conversation history persistence | Currently browser-memory only; add a simple local SQLite table (session_id, messages) so refresh doesn't lose context |
| Basic auth / local accounts | Even a simple session-cookie login with local user table matters for a defence-context demo — shows you thought about it, doesn't need to be elaborate |
| Audit log | Log every prompt, retrieval, and generated deliverable with timestamp + user to a local file/table — directly addresses the "confidential industrial work" framing and is cheap to add |
| Response format / model indicator (exists as domain pill per README) | Keep, extend to also show which tools were called during agentic turns |

**Suggested additional features** (judge-facing, low effort):
- "Explain this drawing" quick-action on uploaded images — one-click OCR/vision summary
- Export a whole conversation + generated deliverables as a zip
- A visible "air-gapped" status indicator (no outbound network calls detected) — strong narrative for the problem statement

---

## 2. Desktop app

Same feature set as the website, plus the agentic tools that need real filesystem access a browser sandbox won't give you.

**Approach**: Tauri (lighter than Electron, smaller binary, matches "on-prem, resource-conscious" positioning) wrapping the existing `index.html`/website UI, with the Rust/JS shell spawning and managing the local FastAPI process (start on app launch, stop on quit). This reuses 100% of the website's frontend and backend — the delta is:

| Feature | Approach |
|---|---|
| Everything the website has | Reuse directly — same FastAPI core, same UI |
| Create/write/edit files | Expose the core's file read/write tool through the agent loop; add a workspace-folder picker in the desktop UI so the user scopes what the agent can touch |
| Codebase-aware editing | `list_dir` + `search_files` (grep-style, e.g. `ripgrep` subprocess) so the agent can locate relevant files in a repo, then propose a diff (unified diff format) for review before `write_file` applies it — mirrors Claude Code/Cursor's review-before-apply pattern |
| Code execution | Same sandboxed subprocess tool from the core, now with a visible output panel |
| Spreadsheet monitoring | `watchdog` on the chosen workspace folder; changes trigger a background agent turn that re-checks the sheet and can push a desktop notification |
| Model/runtime manager | Small settings panel to pull/swap Ollama models and see what's currently loaded — useful for judges to see the "open-weight, swappable" story live |

---

## 3. CLI agent

The most "Claude Code–like" surface — build this directly on `leo/core/` with no HTTP layer for speed.

| Feature | Approach |
|---|---|
| Entry point | Typer or Click CLI (`leo agent "<task>"` or an interactive REPL mode) |
| Read/write files | Core file tools, same sandbox-root restriction, printed diffs before any write, `--yes` flag to skip confirmation for automation/demo runs |
| Code execution | Core sandbox tool, streamed stdout/stderr to terminal |
| Spreadsheet read/write/monitor | Core spreadsheet tool; CLI-specific `leo watch <file>` subcommand for the monitoring case |
| Internal doc search | Core `search_kb` tool, so the agent can ground its own multi-step reasoning against SOPs/manuals without the user manually pasting context |
| Multi-step planning & iteration | The core agent loop, run to completion in the terminal with each step printed (plan → tool call → result → next step) so the judge can literally watch it reason — this is your strongest demo of "actually acting like an agent" |
| Vision/OCR | Same core pipeline; `leo agent "read this drawing and extract the tolerance table" --file drawing.png` |
| Deliverable generation | Same core doc-generation tools; CLI prints the output path when done |
| Session/task memory | Persist plan + step history to a local `.leo/session.json` in the working directory, so a long task can resume if interrupted |

---

## Suggested build order for the remaining hackathon time

1. **RAG pipeline** (website) — everything else depends on `search_kb` existing.
2. **Core tool-calling loop** — file read/write, code exec, spreadsheet, `search_kb` as callable tools; test via CLI agent first since it's the fastest feedback loop (no UI needed).
3. **Document generation tools** (docx/pptx/xlsx) — wire into both the website's deliverable toggle and the CLI/desktop agent.
4. **OCR/vision tier** — Tesseract first (fast win), small VLM escalation second (time-permitting).
5. **Desktop shell** — Tauri wrapper once website + core agent loop are solid; this is mostly packaging, not new logic.
6. **Citations, audit log, auth** — polish pass, valuable for judges but not blocking a working demo.

If time runs out, the CLI agent with steps 1–3 done is a more convincing "agentic" demo on its own than a polished website with no real tool use — prioritize accordingly.
