# Local Secure AI — sample knowledge base

## Privacy principle

All inference stays on the **local machine** via Ollama. Chat content and documents
are not sent to cloud LLM providers.

## Safety principle

The API applies heuristic checks for prompt-injection style inputs and redacts
secret-like patterns in model outputs before returning them to the client.

## Usage

Replace or extend these sample files with your own operational documents
(policies, runbooks, product notes). `POST /v1/ask` will cite matching sources.
