# RAG Evaluation Summary

This document summarizes the current RAG checkpoint before starting the GraphDB / Mini GraphRAG phase.

## What Was Tested

- Chat order in the React UI and frontend message ordering utility.
- Vietnamese answer rendering with diacritics.
- Reasoning questions about the 1986 Doi Moi period.
- Source/citation mapping from retrieved chunks to UI source cards.
- Controlled refusal for out-of-scope historical questions.
- Batch evaluation generation from live targeted runs and JSONL regeneration.

## Latest Targeted Eval Results

The latest targeted runs were executed from `rag-api`:

```powershell
python scripts/batch_eval_history_rag.py --groups Q --run-id pre-graphdb-quick --resume
python scripts/batch_eval_history_rag.py --from-jsonl storage/eval/rag_eval_history_pre-graphdb-quick.jsonl
python scripts/batch_eval_history_rag.py --groups E --run-id pre-graphdb-trap --resume
python scripts/batch_eval_history_rag.py --from-jsonl storage/eval/rag_eval_history_pre-graphdb-trap.jsonl
```

| Run | Total | PASS | WARNING | PASS_TRAP_REFUSAL | FAIL_HALLUCINATION_RISK | Source Mapping Issues |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pre-graphdb-quick | 10 | 6 | 3 | 1 | 0 | 0 |
| pre-graphdb-trap | 10 | 0 | 0 | 10 | 0 | 0 |

Additional reference runs from the stabilization phase:

- `quick-source-fix`: total 10; Q10 `PASS_TRAP_REFUSAL`; source mapping issue count 0.
- `trap-after-refusal-fix`: E01-E10 `PASS_TRAP_REFUSAL`; `FAIL_HALLUCINATION_RISK` 0.
- `c-source-fix`: source mapping issue count 0.
- `a-source-fix`: still WARNING because person-specific queries are not directly supported by the current document chunks.

## Anti-Hallucination Result

The targeted Q and E runs both reported hallucination risk count 0.

Trap questions about Dinh Bo Linh and earlier Vietnamese history were refused instead of answered from outside knowledge when the active document only covered 1986-2000.

## Source Mapping Result

The latest targeted runs reported source mapping issue count 0.

For answerable questions, source metadata is returned and rendered in the UI with file name, page, chunk, score, support level, and preview. For controlled refusals, sources are intentionally absent or shown only as related insufficient chunks.

## Remaining Warnings

The quick run has 3 WARNING results. These are not hallucination failures; they indicate partial or insufficient-context answers where the system avoided overclaiming.

The older `a-source-fix` run remains WARNING for person-specific questions such as Nguyen Van Linh, Do Muoi, and Vo Van Kiet. The current chunk set is not strong enough for every named-person query.

## Recommended Next Step

Start the GraphDB / Mini GraphRAG phase after this checkpoint.

The next phase should improve person-event-time relation retrieval while preserving:

- citation/source mapping,
- controlled refusal,
- chat order,
- batch evaluation,
- Vietnamese answer quality.
