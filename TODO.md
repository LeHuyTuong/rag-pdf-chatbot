# TODO

## Not implemented yet
- OCR for scanned PDFs; current behavior returns warning: "PDF may be scanned. OCR is not implemented yet."
- Full BM25 hybrid search; MVP includes vector search plus keyword_score.
- Advanced cross-encoder reranking.
- Multi-document chat across several PDFs in one question.
- Admin source trust scoring.

## Known issues
- If no LLM API key/base URL is configured, the LLM service uses an extractive context-based fallback instead of a generative answer.
- Evaluation sample questions require an ingested document with matching `document_id` or editing `eval_questions.json` after upload.

## Future improvements
- Add async ingestion queue.
- Add streaming responses.
- Add semantic evaluation model.
- Add document deletion cleanup in Qdrant and storage.
