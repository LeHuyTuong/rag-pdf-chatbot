# Google Scholar Manual Search Protocol

Google Scholar is intentionally not scraped by this pipeline. Run these exact searches manually,
export permitted citation metadata, and record any newly screened items in `data/papers_raw.csv`
with `source_database=Google Scholar (manual)` before rerunning downstream stages.

- `("Vietnamese" AND "text embedding" AND "retrieval")`
- `("Vietnamese" AND "semantic search" AND "embedding")`
- `("Vietnamese" AND "information retrieval" AND "neural retrieval")`
- `("Vietnamese" AND "sentence embedding" AND "PhoBERT")`
- `("Vietnamese" AND "SBERT" AND "retrieval")`
- `("multilingual embedding" AND "Vietnamese" AND "retrieval")`
- `("BGE-M3" AND "Vietnamese" AND "retrieval")`
- `("multilingual-e5" AND "Vietnamese")`
- `("VN-MTEB" OR "Vietnamese Massive Text Embedding Benchmark")`
- `("MTEB" AND "Vietnamese" AND "embedding")`
- `("Vietnamese legal retrieval" OR "Vietnamese legal text retrieval")`
- `("Vietnamese medical retrieval" OR "Vietnamese biomedical retrieval")`
- `("Vietnamese news retrieval")`
- `("Vietnamese history" AND "retrieval" AND "embedding")`
- `("RAG" AND "Vietnamese" AND "embedding model")`
