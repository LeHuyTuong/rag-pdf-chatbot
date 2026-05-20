# Re-ingestion After Text/Vector Fixes

Use these steps when retrieved chunk previews show Vietnamese text without diacritics, mojibake, or old low-quality payloads from a previous ingest.

1. Stop the services that write to Qdrant.
2. Clear the old vector collection, for example delete the `rag_chunks` collection from Qdrant or remove the configured local Qdrant path.
3. Start Qdrant and the RAG API again.
4. Upload or ingest the PDF again so chunks are embedded from the original Vietnamese text with diacritics.
5. Ask a debug question and inspect the retrieval report or logs. Retrieved chunk previews should contain text such as `Đổi mới`, `Đại hội VI`, `khủng hoảng kinh tế - xã hội`.
6. If previews are still accent-stripped, inspect the PDF extraction/chunking report before trusting answer quality.

Code changes prevent future ingest from stripping accents, but they cannot repair vectors and payloads already stored with damaged text.
