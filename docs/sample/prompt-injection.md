# Prompt injection (high-level)

Prompt injection is an attack technique where untrusted text tries to override
an application's instructions to a language model.

## Defensive ideas (product level)

- Separate system instructions from user content
- Detect common jailbreak / override phrases
- Constrain tools the model can call (allowlist)
- Log and audit model + tool activity
- Prefer retrieval from trusted local documents for factual answers

This file is part of the local knowledge base for RAG. It does not provide exploit steps.
