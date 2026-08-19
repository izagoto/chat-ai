# Alder AI

On-premise AI chatbot for your own files. Powered by [Ollama](https://ollama.com) — no cloud LLM, data stays on this machine.

The name **Alder AI** is a rooted tree plus AI: local, durable, not a cloud brand. Upload documents, images, or a public URL, then ask questions in chat. Alder AI retrieves relevant excerpts (RAG), cites the source, and answers with a local model.

## What this project is

Alder AI is a **local-first assistant**: FastAPI backend + React UI + SQLite + Ollama. It is meant for private document Q&A (notes, PDFs, spreadsheets, Word files), not a hosted SaaS chatbot and not a forensics/case-management tool.

Typical flow:

1. Sign in
2. Start a chat (threads are saved per user)
3. Attach a file in chat, or add files/URLs on the Documents page
4. Ask — Alder AI indexes in the background, then answers from retrieved chunks plus general knowledge
5. Edit a user message (pencil on hover) to regenerate from that point, like ChatGPT

```
Browser (React / Vite)
        │  /v1  and  /health
        ▼
FastAPI  ──►  SQLite (users, conversations)
        ├──►  document store (chunks + optional embeddings)
        ├──►  ingest worker (extract → index)
        └──►  Ollama (chat, embeddings, optional vision)
```

## Features

| Area | What you get |
|------|----------------|
| Auth | Email + password login; seed user from `.env` |
| Chat | Streaming replies, Markdown (headings, lists, tables), edit user prompt and regenerate |
| Conversations | Persisted threads, sidebar list, New chat, delete |
| Documents | Per-user library; upload, list, delete |
| File types | PDF, DOCX, Excel (`.xlsx`/`.xls`), CSV, TXT, MD, JSON, common images |
| URLs | Paste a public `http`/`https` link; private/localhost IPs are blocked (SSRF protection) |
| RAG | Chunked index, embeddings when available, keyword fallback, citations (file + page/sheet/URL) |
| Images | OCR and optional vision (`llava`) when the model is installed |
| Ingest | Async: upload returns `processing`, then `ready` or `failed` |

**Not in the product yet:** video analysis (code exists but is deferred), Postgres/pgvector, cloud models.

## Stack

| Layer | Choice |
|-------|--------|
| API | Python 3.12+, FastAPI, Uvicorn |
| UI | React 19, Vite, React Router |
| DB | SQLite (`data/alder.db`) |
| LLM | Ollama (`llama3.2:3b` by default) |
| Embeddings | `nomic-embed-text` (optional but recommended) |

## Requirements

- [Ollama](https://ollama.com) running on `127.0.0.1:11434`
- Python 3.12+ (project is tested with a local `.venv`)
- Node.js 20+ for the frontend
- Optional: Tesseract for image OCR; `llava` for vision captions

**RAM:** `llama3.2:3b` (~2 GB) fits an 8 GB machine. Use `llama3.2:8b` (or similar) if you have 16 GB+ — answers will be stronger.

## Quick start

### 1. Ollama

```bash
ollama serve
ollama pull llama3.2:3b
ollama pull nomic-embed-text   # embeddings for better RAG
# optional
# ollama pull llama3.2:8b
# ollama pull llava
```

### 2. Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit if needed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 3. Frontend (development)

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/v1` and `/health` to port 8000.

Production UI (FastAPI serves `frontend/dist`):

```bash
cd frontend && npm run build
# then use http://127.0.0.1:8000
```

## Default login

| Field | Value |
|-------|-------|
| Email | `user@alder.ai` |
| Password | `Alder@2026` |

Change `AUTH_EMAIL` / `AUTH_PASSWORD` / `AUTH_SECRET` in `.env`. The seed user is created on first start if that email is not already in the database.

## How chat uses your files

Alder AI does **not** dump whole files into the model. On upload (or URL fetch):

1. Text is extracted (PDF pages, Word body, Excel sheets, HTML→text, etc.)
2. Content is split into chunks and stored under a **per-user collection**
3. On each question, the top matching chunks are added to the system context
4. The UI shows **citations** (filename and location) when those chunks were used

Casual greetings skip retrieval. Questions about files, links, or specific facts trigger RAG.

Ingest limits (defaults): 25 MB per upload, 5 MB per fetched URL, 15 s URL timeout. Only `http`/`https` on ports 80/443; localhost, `.local`, and private IPs are rejected.

## Configuration

Copy [`.env.example`](.env.example) to `.env`. Important keys:

| Key | Default | Notes |
|-----|---------|-------|
| `OLLAMA_MODEL` | `llama3.2:3b` | Chat model; pull it with Ollama first |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Used when `RAG_USE_EMBEDDINGS=true` |
| `OLLAMA_VISION_MODEL` | `llava` | Image captions if installed |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Raise if large models are slow |
| `DATABASE_URL` | `sqlite:///data/alder.db` | Users and conversations |
| `DOCUMENTS_PATH` | `data/documents` | Indexed uploads (per collection) |
| `AUTH_ENABLED` | `true` | Login required for the UI |
| `MAX_UPLOAD_BYTES` | `26214400` | 25 MB |
| `URL_MAX_BYTES` | `5242880` | 5 MB fetched pages |

If `/health` reports `degraded` and mentions a missing model, run `ollama pull <name>` and keep `ollama serve` running.

## Main API

All `/v1/*` routes (except login) expect `Authorization: Bearer <token>` when auth is enabled.

| Action | Endpoint |
|--------|----------|
| Health | `GET /health` |
| Login | `POST /v1/auth/login` |
| Current user | `GET /v1/auth/me` |
| Chat | `POST /v1/chat` |
| Chat stream (SSE) | `POST /v1/chat/stream` |
| Conversations | `GET/POST /v1/conversations`, `GET/DELETE /v1/conversations/{id}` |
| Upload file | `POST /v1/documents` (multipart `file`) |
| Ingest URL | `POST /v1/urls` `{ "url": "https://..." }` |
| List / delete documents | `GET /v1/documents`, `DELETE /v1/documents/{id}` |
| Ask over static `docs/` | `POST /v1/ask` |
| Analyze image | `POST /v1/analyze/image` |
| System prompt | `GET/PUT /v1/prompt` |

`POST /v1/chat` and `/v1/chat/stream` accept `edit_message_id` to replace a user message, drop later turns, and generate a new reply.

### Example

```bash
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@alder.ai","password":"Alder@2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -sS -X POST http://127.0.0.1:8000/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@notes.txt"

curl -sS -X POST http://127.0.0.1:8000/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Ringkas dokumen saya","use_documents":true}'
```

## Project layout

```
app/                 FastAPI app (API, services, models)
  api/               HTTP routes
  services/          Ollama, RAG, extractors, ingest worker, URL fetch
  db/                SQLite session + schema init
frontend/            React SPA (Vite)
docs/                PRD and sample files
data/                Created at runtime (DB + document index)
tests/               pytest
scripts/smoke.sh     Quick live API checks
```

Product notes: [docs/PRD.md](docs/PRD.md).

## Tests

```bash
source .venv/bin/activate
pytest -q
```

With the API already running:

```bash
bash scripts/smoke.sh
```

## License / privacy

This is a local workspace app. Uploads and chat history live in `data/` on the host. Nothing is sent to a cloud LLM as long as you only use Ollama on this machine.
