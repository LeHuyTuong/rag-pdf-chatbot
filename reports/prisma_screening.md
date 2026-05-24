# PRISMA-Style Screening Report

## Flow Summary

| Stage | Records |
| --- | ---: |
| Records identified from publication database/API searches before deduplication | 640 |
| Records after DOI/title/arXiv/Semantic Scholar ID deduplication | 369 |
| Records screened by title/abstract and any legally obtained PDF text | 369 |
| Records excluded or classified as peripheral | 334 |
| Open-access full texts downloaded and available for assessment | 42 |
| Papers included as core literature | 15 |

`data/search_log.csv` records each API request and count. Hugging Face model-card results are
stored as supporting model sources and are not counted as publication records above. A successful
PDF download denotes full text available for assessment; absence of a PDF is not treated as proof
that a paper is paywalled.

## Databases And Sources

ACL Anthology, Crossref, DBLP, Hugging Face model cards, OpenAlex, OpenReview, Semantic Scholar, arXiv. Google Scholar is a manual supplementary search only; this pipeline does not scrape it.

## Search Strings

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

## Inclusion Criteria

- Text/sentence embeddings, neural or semantic retrieval, RAG retrieval, information retrieval, or embedding benchmark evaluation.
- Vietnamese content, a multilingual setting relevant to Vietnamese, or a Vietnamese-specific model/dataset.
- Reports or exposes evaluation methodology/metrics, datasets, models, or domain-specific retrieval evidence.
- Publications from 2019 onward are preferred; foundational earlier work remains eligible when relevant.

## Exclusion Criteria

- No embedding or retrieval relevance identifiable in metadata or legally accessed full text.
- Generation/chatbot-only work without retrieval evaluation.
- English-only retrieval without Vietnamese or multilingual relevance.
- No usable abstract or accessible metadata.
- Duplicate records removed using DOI, normalized title, arXiv ID, or Semantic Scholar paper ID.
- Blog/model-card sources are supporting sources rather than core papers.

## Screening And Ranking Procedure

`scripts/screen_papers.py` implements the declared 0-10 score. It records the reason signals in
`exclusion_reason`, ranks eligible records, selects up to 15 core records (including eligible
multilingual model/benchmark background) and up to 20 supporting records, and treats remaining
eligible records as peripheral pending manual screening. Selection is an initial machine-assisted
screening decision and should be audited before submission.
