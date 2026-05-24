# Research Proposal

## Title

Multilingual Versus Vietnamese-Specific Embeddings for Vietnamese Text Retrieval Across News, Legal, Medical, and History Domains

## Problem Statement

Embedding selection for Vietnamese retrieval systems requires domain-stratified comparative
evidence. The accompanying literature matrix records source evidence for candidate prior work, but
does not yet establish a controlled comparison over all four proposed domains. Matrix basis: [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]; [Dang2026_P452D138CC5; P452D138CC5]; [Pham2026_P0B2625DE40; P0B2625DE40]; [Le2025_P0361B383C0; P0361B383C0]; [Enevoldsen2025_P048819CB98; P048819CB98]; [Nguyen2025_P06356296BC; P06356296BC]; [Nguyen2025_P761355BB9F; P761355BB9F]; [Zhang2024_P9F643D4414; P9F643D4414]; [Ba2024_P1E2585E7BA; P1E2585E7BA]; [Duc2024_P5182A0032F; P5182A0032F]; [Wang2024_P47282B6184; P47282B6184]; [Tien2024_PC628139497; PC628139497]; [Bac2024_P7340A11077; P7340A11077]; [Pham2022_PD63FF37D74; PD63FF37D74]; [Vu2011_PF27F8656D0; PF27F8656D0].

## Research Question

How do multilingual embedding models perform compared with Vietnamese-specific embedding models on
Vietnamese text retrieval tasks across news, legal, medical, and history domains?

## PICO

| Element | Specification |
| --- | --- |
| Population | Vietnamese text retrieval tasks across news, legal, medical, and history domains |
| Intervention | Vietnamese-specific embedding models |
| Comparison | Multilingual embedding models |
| Outcome | nDCG@10, Recall@10, MRR, MAP, latency, model size, and deployment cost |

## Motivation

A retrieval model suitable for one Vietnamese domain may not transfer uniformly to terminology,
document structure, and query style in another. A matched and transparent benchmark can separate
model-family effects from domain and corpus effects.

## Research Gap

The gap to test is a controlled, same-protocol comparison of multilingual and Vietnamese-specific
embeddings across all four Vietnamese domains. This is a hypothesis for empirical validation; the
screening artifacts do not assert absence of prior work.

## Hypotheses

- **H0:** There is no significant performance difference between multilingual embedding models and Vietnamese-specific embedding models on Vietnamese text retrieval tasks across domains.
- **H1:** Vietnamese-specific embedding models perform significantly better than multilingual embedding models on at least one Vietnamese domain-specific retrieval task.

## Variables

| Type | Variables |
| --- | --- |
| Independent | embedding model family and model identity; document domain |
| Dependent | nDCG@10, Recall@10, MRR, MAP, query latency, index size/model size, estimated deployment cost |
| Controlled | corpus split, relevance judgments, text normalization, chunking policy, embedding dimensional handling, vector index/search settings, hardware, batching |

## Proposed Methodology

1. Complete manual full-text coding from `data/literature_matrix.csv`, validating dataset and metric evidence against each cited paper.
2. Obtain or construct legally usable Vietnamese retrieval corpora with documented provenance and relevance judgments for each domain.
3. Freeze train/development/test splits and a single preprocessing and indexing protocol.
4. Encode and retrieve with each selected model under equivalent conditions; log hardware, index configuration, latency, and model footprint.
5. Report per-domain metrics and macro summaries, with paired significance testing on per-query outcomes and multiple-comparison handling.
6. Release scripts, configuration, judgment provenance, and result tables subject to dataset licenses.

## Model List

Candidate families to verify during manual coding include multilingual models detected in screened
sources (`BGE-M3`, `multilingual-e5`, `LaBSE`, `XLM-R`) and Vietnamese-specific encoders derived
from or explicitly trained for Vietnamese (including any source-supported `PhoBERT` embedding
variant). Inclusion in experiments requires a traceable model card or paper and license review.

## Dataset And Domain Plan

| Domain | Corpus Requirement | Judgment Plan |
| --- | --- | --- |
| News | Vietnamese articles with query-document relevance pairs | Reuse licensed benchmark if verified; otherwise construct and adjudicate |
| Legal | Vietnamese statutes/cases or legal QA retrieval corpus | Preserve versioned legal sources and expert/annotated relevance |
| Medical | Licensed Vietnamese health/biomedical material | Privacy/licensing review and domain-informed adjudication |
| History | Vietnamese historical reference text | Document provenance and query relevance annotation |

## Metrics

Primary effectiveness metrics are nDCG@10 and Recall@10; secondary effectiveness metrics are MRR
and MAP. Efficiency measures are latency under stated hardware/batch conditions, model/index size,
and estimated deployment cost.

## Expected Output

- A source-audited systematic literature review and PRISMA-style screening record.
- A reproducible four-domain Vietnamese retrieval benchmark protocol and, where licensing permits, artifacts.
- Per-model, per-domain effectiveness and efficiency results with statistical testing.
- A documented recommendation conditioned on domain and deployment constraints rather than an unsupported universal ranking.
