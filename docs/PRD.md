# PRD — Local Secure AI

**Product:** Local Secure AI  
**Type:** Production-oriented local LLM service (API + Web UI)  
**Version:** 0.1  
**Privacy stance:** Inference dan dokumen tetap di mesin/host lokal (Ollama). Tidak ada cloud LLM.

---

## 1. Problem

Organisasi dan individu sering membutuhkan asisten LLM tanpa mengirim data ke pihak ketiga. Solusi cloud mudah, tetapi bermasalah untuk:

- Data internal / sensitif
- Lingkungan terbatas jaringan
- Kebutuhan audit request dan kontrol safety di lapisan aplikasi

---

## 2. Goals

| Goal | Success metric |
|------|----------------|
| Chat lokal streaming | Endpoint stabil; first token usable pada model target |
| RAG dengan sitasi | Jawaban menyertakan `sources[]` dari knowledge base lokal |
| Safety layer | Pola injection terdeteksi; mode strict memblokir |
| Observability | Setiap request punya `request_id` + log latency |
| Operasional lokal | Dapat dijalankan dengan Ollama + satu proses FastAPI |

### Non-goals (v0.1)

- Fine-tuning model
- Multi-tenant SaaS
- Agent dengan eksekusi shell / network arbitrary
- Moderasi konten setara produk enterprise

---

## 3. Users

1. **Operator / engineer** — deploy, konfigurasi model, isi knowledge base.
2. **End user internal** — chat dan tanya dokumen lewat UI atau API.
3. **Security-minded stakeholder** — butuh privacy by default + jejak request.

---

## 4. User stories

### Must-have (v0.1)

| ID | Story | Acceptance |
|----|-------|------------|
| US-01 | User chat ke model lokal via API/UI | `POST /v1/chat` mengembalikan jawaban saat Ollama up |
| US-02 | User menerima streaming token | `POST /v1/chat/stream` mengirim SSE sampai `done` |
| US-03 | User bertanya berbasis dokumen lokal | `POST /v1/ask` + `sources[]` |
| US-04 | Sistem memfilter prompt berbahaya | Mode `strict`: injection → 403 |
| US-05 | Sistem meredact pola secret di output | Pattern key/password di-mask |
| US-06 | Operator cek health stack | `GET /health` |
| US-07 | Operator lacak request | `X-Request-ID` + structured log |

### Should-have (berikutnya)

| ID | Story |
|----|-------|
| US-08 | Rate limit per IP / API key |
| US-09 | Embedding-based retrieval |
| US-10 | Session persistensi |
| US-11 | Tool allowlist + audit log |

---

## 5. Functional requirements

- **FR-1 Chat:** message + optional session + safety_mode → Ollama chat
- **FR-2 Streaming:** SSE delta + done/error
- **FR-3 RAG:** index `docs/` (`.md`/`.txt`), retrieve top-k, jawab dengan sitasi
- **FR-4 Safety:** input heuristics + output secret redact
- **FR-5 Observability:** request_id middleware + latency log
- **FR-6 Models:** list dari Ollama; active model dari env

---

## 6. Non-functional requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Privacy | Tidak ada outbound LLM selain Ollama lokal |
| NFR-2 | Reliability | Ollama down → error jelas (503/504) |
| NFR-3 | Security | Optional API key; CORS terbatas; no open proxy |
| NFR-4 | Operability | Satu command `uvicorn` + `ollama serve` |
| NFR-5 | Testability | Unit test safety + RAG retrieve + health |

---

## 7. API (ringkas)

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat`
- `POST /v1/chat/stream`
- `POST /v1/ask`
- `DELETE /v1/sessions/{session_id}`

Detail field: lihat OpenAPI di `/docs` saat server berjalan.

---

## 8. Architecture

```
Client → FastAPI → Safety / Session / RAG → Ollama (localhost)
                      └─ knowledge: docs/
```

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Resource host terbatas | Default model kecil; dokumentasikan trade-off |
| RAG kualitas rendah tanpa embedding | Roadmap embedding; dokumentasikan batasan v0.1 |
| Eksposur tanpa rate limit | Dokumentasikan; sarankan API key + reverse proxy |

---

## 10. Narrative

> Local Secure AI adalah layanan LLM on-premise ringan: chat streaming, RAG bersitasi, safety guardrails, dan request tracing — untuk pemakaian nyata yang memprioritaskan privasi data.
