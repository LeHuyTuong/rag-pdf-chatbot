# Pre-GraphDB RAG Checkpoint

This checkpoint closes the current RAG phase before any GraphDB or GraphRAG implementation begins.

## Current Stable Status

- React frontend, Spring Boot backend, and FastAPI RAG service are wired for document chat.
- Upload/ingest, chunking, embedding, retrieval, answer generation, and source display are in place.
- Chat message order is fixed so new turns append at the bottom.
- Vietnamese answers with diacritics are covered by tests and browser evidence.
- Controlled refusal is active for out-of-scope questions.
- Batch evaluation can generate TXT, CSV, and JSONL outputs and regenerate reports from JSONL.
- Browser screenshots were captured from a real Chrome session against running local services.

## Verification Snapshot

Automated tests:

- RAG API: `python -m py_compile scripts/batch_eval_history_rag.py` passed.
- RAG API: `python -m pytest tests` passed with 24 passed, 1 skipped.
- Frontend: `npm --prefix frontend run test:chat-order` passed.
- Frontend: `npm --prefix frontend run build` passed.
- Backend: `.\mvnw.cmd test` passed after setting `JAVA_HOME=C:\Program Files\Java\jdk-21`.

Targeted evaluation:

- `pre-graphdb-quick`: 10 total, 6 PASS, 3 WARNING, 1 PASS_TRAP_REFUSAL, 0 hallucination risk.
- `pre-graphdb-trap`: 10 total, 10 PASS_TRAP_REFUSAL, 0 hallucination risk.

Screenshots:

- `docs/screenshots/01-chat-order.png`
- `docs/screenshots/02-rag-reasoning-citation.png`
- `docs/screenshots/03-controlled-refusal.png`
- `docs/screenshots/04-evaluation-report.png`

## Known Limitations

- Named-person questions can still produce WARNING when retrieved chunks do not directly support the requested details.
- The current vector-only retrieval is weaker for person-event-time relationship questions.
- The system may return partial answers when evidence is related but incomplete.
- Local end-to-end demo requires the RAG API, backend, frontend, vector store, and a completed document.

## Why GraphDB Is Next

The current RAG system can answer broad document-grounded questions and refuse out-of-scope traps. The remaining hard cases are relationship-heavy questions such as:

- which person held which office,
- which leader relates to which event,
- which event happened in which year,
- how a person, policy, and period connect.

A Mini GraphRAG layer can add entity and relation retrieval on top of the current chunk retrieval, without replacing the anti-hallucination guard.

## What Not To Break In The GraphDB Phase

- Citation/source mapping must remain visible in API responses and UI source cards.
- Controlled refusal must remain the default for unsupported questions.
- Chat order must continue to append user and assistant turns at the bottom.
- Batch evaluation must keep working for Q, C, A, and E groups.
- Vietnamese answer quality and diacritics must remain covered.
- GraphDB/Neo4j code should be additive and should not remove the existing vector RAG path.
