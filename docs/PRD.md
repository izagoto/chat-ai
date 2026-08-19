# PRD — Alder AI

**Product:** Alder AI  
**Type:** On-premise AI document chatbot (Ollama)  
**Version:** 0.2

## Problem

Users need a private chatbot that can answer questions about their own files (PDF, Excel, TXT, JSON, images) without sending data to a cloud LLM.

## Solution

Alder AI is a local chat app: upload documents and images, then ask questions. Answers use retrieved excerpts from in
dexed uploads plus a local Ollama model.

## Goals

- Chat UI with streaming replies
- Upload PDF, Excel/CSV, TXT/MD, JSON, and common image formats
- RAG over uploaded files
- Optional image OCR / vision analysis (when Ollama vision model is available)
- Email/password login for a local professional workspace

## Non-goals

- Forensic case / device / suspect management
- WhatsApp msgstore extraction
- Cloud LLM providers

## User stories

| ID | Story | API / UI |
|----|-------|----------|
| US-01 | Sign in | Login page, `POST /v1/auth/login` |
| US-02 | Chat with Alder AI | Chat page, `POST /v1/chat` / `/v1/chat/stream` |
| US-03 | Upload documents | Documents page / chat attach, `POST /v1/documents` |
| US-04 | List / delete documents | `GET/DELETE /v1/documents` |
| US-05 | Analyze an image | `POST /v1/analyze/image` (also used on image ingest) |

## Functional requirements

- **FR-1 Auth:** Bearer session tokens; seed user from env
- **FR-2 Documents:** Extract text, chunk, optional embeddings, keyword fallback
- **FR-3 Chat:** System prompt as Alder AI assistant; retrieve top chunks into context
- **FR-4 Safety:** Input heuristics + output redaction
- **FR-5 SPA:** React + Vite served from FastAPI `frontend/dist`

## Architecture (high level)

```
User → Alder AI UI → FastAPI
                 ├─ /v1/documents → extractors → document_store
                 ├─ /v1/chat(/stream) → document_store retrieve → Ollama
                 └─ /v1/analyze/image → OCR / vision → Ollama
```

## Success criteria

- Login works with seed credentials
- Uploaded JSON/TXT appears in document list with chunks > 0
- Chat returns 200 when Ollama is up (or clear 503 when down)

## One-liner

> Alder AI is an on-premise AI chatbot: upload documents and images, then chat with them using a local Ollama model — data stays on your machine.
