# Alder AI — sample knowledge base

## Privacy principle

All inference stays on the **local machine** via Ollama. Chat content and documents
are not sent to cloud LLM providers.

## Safety principle

The API applies heuristic checks for prompt-injection style inputs and redacts
secret-like patterns in model outputs before returning them to the client.

## Usage

Replace or extend these sample files with your own documents
(policies, runbooks, product notes). `POST /v1/ask` will cite matching sources
under `docs/`. Uploaded files use `POST /v1/documents` and chat RAG instead.
