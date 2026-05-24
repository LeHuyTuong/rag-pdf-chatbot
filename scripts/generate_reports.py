"""Generate PRISMA, review/proposal drafts, model table, and BibTeX."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from literature_common import (
    DATA_DIR,
    REFERENCES_DIR,
    REPORTS_DIR,
    SEARCH_STRINGS,
    authors_to_bibtex,
    ensure_dirs,
    read_csv,
)


def cite(row: pd.Series) -> str:
    return f"[{row['citation_key']}; {row['paper_id']}]"


def joined_citations(rows: pd.DataFrame, limit: int | None = None) -> str:
    if rows.empty:
        return "No source coded in the current matrix."
    selected = rows if limit is None else rows.head(limit)
    return "; ".join(cite(row) for _, row in selected.iterrows())


def prisma() -> None:
    raw = read_csv(DATA_DIR / "papers_raw.csv")
    screened = read_csv(DATA_DIR / "screened_papers.csv")
    core = read_csv(DATA_DIR / "core_papers.csv")
    logs = read_csv(DATA_DIR / "search_log.csv")
    pdfs = read_csv(DATA_DIR / "pdf_download_log.csv")
    publications = logs[logs["source_database"] != "Hugging Face model cards"] if not logs.empty else logs
    identified = int(pd.to_numeric(publications.get("records_returned", []), errors="coerce").fillna(0).sum())
    fulltext = int((pdfs.get("download_status", pd.Series(dtype=str)) == "downloaded").sum())
    excluded = int(screened["screening_status"].isin(["exclude", "peripheral"]).sum())
    databases = ", ".join(sorted(logs["source_database"].unique())) if not logs.empty else ""
    text = f"""# PRISMA-Style Screening Report

## Flow Summary

| Stage | Records |
| --- | ---: |
| Records identified from publication database/API searches before deduplication | {identified} |
| Records after DOI/title/arXiv/Semantic Scholar ID deduplication | {len(raw)} |
| Records screened by title/abstract and any legally obtained PDF text | {len(screened)} |
| Records excluded or classified as peripheral | {excluded} |
| Open-access full texts downloaded and available for assessment | {fulltext} |
| Papers included as core literature | {len(core)} |

`data/search_log.csv` records each API request and count. Hugging Face model-card results are
stored as supporting model sources and are not counted as publication records above. A successful
PDF download denotes full text available for assessment; absence of a PDF is not treated as proof
that a paper is paywalled.

## Databases And Sources

{databases}. Google Scholar is a manual supplementary search only; this pipeline does not scrape it.

## Search Strings

""" + "\n".join(f"- `{query}`" for query in SEARCH_STRINGS) + """

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
"""
    (REPORTS_DIR / "prisma_screening.md").write_text(text, encoding="utf-8")


def literature_review() -> None:
    matrix = read_csv(DATA_DIR / "literature_matrix.csv")
    core = read_csv(DATA_DIR / "core_papers.csv")
    papers = core.merge(matrix[["paper_id", "citation_key"]], on="paper_id", how="left")
    evidence = matrix.set_index("paper_id") if not matrix.empty else pd.DataFrame()
    table_rows = []
    for _, row in papers.iterrows():
        table_rows.append(
            f"| {row['paper_id']} | {row['title']} | {row['domain']} | "
            f"{row['models_mentioned'] or 'Not automatically identified'} | "
            f"{row['metrics_mentioned'] or 'Not automatically identified'} | {cite(row)} |"
        )
    domain_lines = []
    for domain in ("news", "legal", "medical", "history"):
        subset = papers[papers["domain"].str.contains(domain, case=False, na=False)]
        domain_lines.append(
            f"- **{domain.title()}**: {len(subset)} core record(s) tagged by metadata/full-text term detection. "
            f"{joined_citations(subset)}"
        )
    metrics_rows = []
    for _, row in papers.iterrows():
        if row["metrics_mentioned"]:
            metrics_rows.append(
                f"| {row['paper_id']} | {row['metrics_mentioned']} | Verify definitions and values in source text. | {cite(row)} |"
            )
    references = []
    for _, row in papers.iterrows():
        details = f"{row['authors']} ({row['year']}). *{row['title']}*. {row['venue']}."
        if row["doi"]:
            details += f" DOI: https://doi.org/{row['doi']}."
        details += f" Source record: {row['paper_id']}."
        references.append(f"- {details}")
    text = f"""# Literature Review Draft: Vietnamese Text Retrieval Embeddings Across Domains

## 1. Introduction

This draft addresses whether Vietnamese-specific embedding models outperform multilingual embedding
models for Vietnamese retrieval in news, legal, medical, and history domains. It is generated from
the screened records and evidence excerpts in `data/literature_matrix.csv`. It deliberately does
not assert a model winner until metric values and experimental comparability are manually verified
against full text. Evidence inventory: {joined_citations(papers)}.

## 2. Background On Multilingual And Vietnamese-Specific Embedding Models

The current core set was selected because its retrievable metadata or open-access text identifies
Vietnamese/multilingual embedding, retrieval, or benchmark relevance. The table reports detected
terms only; a blank cell does not establish absence in the paper.

| ID | Paper | Detected Domain | Detected Models | Detected Metrics | Evidence Key |
| --- | --- | --- | --- | --- | --- |
""" + "\n".join(table_rows) + f"""

## 3. Vietnamese Text Retrieval Benchmarks And Datasets

Dataset names extracted during screening should be checked against dataset definitions, splits, and
Vietnamese coverage before benchmark design. Current dataset-term evidence is linked below:

| Paper ID | Detected Dataset Terms | Citation |
| --- | --- | --- |
""" + "\n".join(
        f"| {row['paper_id']} | {row['datasets_mentioned'] or 'No controlled-vocabulary match'} | {cite(row)} |"
        for _, row in papers.iterrows()
    ) + f"""

## 4. Model Comparison Themes

### 4.1 Multilingual Embedding Models

The evidence matrix identifies multilingual-model terms for manual extraction of training scope,
language coverage, and reported retrieval results. The relevant source-linked records are:
{joined_citations(papers[papers['models_mentioned'].str.contains('BGE|multilingual|LaBSE|XLM|mBERT|E5', case=False, na=False)])}

### 4.2 Vietnamese-Specific Embedding Models

Records tagged with Vietnamese/PhoBERT or Vietnamese retrieval terminology provide the starting
point for identifying monolingual baselines. A valid comparative claim requires matched corpora,
query sets, and metrics, which are not inferred automatically here. Sources:
{joined_citations(papers[papers['title'].str.contains('Vietnam|PhoBERT', case=False, na=False) | papers['abstract'].str.contains('Vietnam|PhoBERT', case=False, na=False)])}

### 4.3 Domain-Specific Retrieval: News, Legal, Medical, History

""" + "\n".join(domain_lines) + f"""

These counts are classifications in this screening dataset, not findings about retrieval quality.

## 5. Evaluation Metrics Used In Prior Work

Metric mentions extracted from metadata or available PDF text are listed for full-text coding.
Performance numbers are intentionally not transcribed without table-level verification.

| Paper ID | Metric Terms Located | Coding Note | Citation |
| --- | --- | --- | --- |
""" + ("\n".join(metrics_rows) if metrics_rows else "| - | No metric terms automatically located | Manual assessment required | - |") + f"""

## 6. Research Gaps

The present automated matrix has not coded a validated, controlled head-to-head result across all
four target domains. That is a proposed review/benchmark question rather than a claim that no such
study exists. The immediate gap-coding task is to verify each core paper's dataset domain,
Vietnamese-language composition, model comparators, metric definitions, and numerical results.
Evidence base for this coding task: {joined_citations(papers)}.

## 7. Proposed Research Direction

A subsequent empirical benchmark should compare the same Vietnamese query-document relevance sets
with multilingual and Vietnamese-specific encoders, stratified by news, legal, medical, and
history domains. It should report nDCG@10, Recall@10, MRR, MAP, latency, model size, and deployment
cost, and should preregister significance testing before interpreting H0/H1.

## 8. Conclusion

This reproducible screening run supplies a traceable candidate set, legally acquired open-access
full texts where available, and evidence excerpts for manual synthesis. Comparative conclusions are
deferred until numerical evidence is verified in the cited source papers.

## 9. References

""" + "\n".join(references) + "\n"
    (REPORTS_DIR / "literature_review_draft.md").write_text(text, encoding="utf-8")


def proposal() -> None:
    matrix = read_csv(DATA_DIR / "literature_matrix.csv")
    cited = joined_citations(matrix)
    text = f"""# Research Proposal

## Title

Multilingual Versus Vietnamese-Specific Embeddings for Vietnamese Text Retrieval Across News, Legal, Medical, and History Domains

## Problem Statement

Embedding selection for Vietnamese retrieval systems requires domain-stratified comparative
evidence. The accompanying literature matrix records source evidence for candidate prior work, but
does not yet establish a controlled comparison over all four proposed domains. Matrix basis: {cited}.

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
"""
    (REPORTS_DIR / "research_proposal.md").write_text(text, encoding="utf-8")


def model_table() -> None:
    matrix = read_csv(DATA_DIR / "literature_matrix.csv")
    entries = []
    for _, row in matrix.iterrows():
        model_text = row["models_compared"]
        if model_text.startswith("Detected terms only; verify comparison: "):
            model_text = model_text.split(": ", 1)[1]
        else:
            model_text = ""
        models = [m.strip() for m in model_text.split(";") if m.strip()]
        if not models:
            entries.append(("Not automatically identified", row))
        else:
            entries.extend((model, row) for model in models)
    header = """# Model Comparison Evidence Table

Fields not supported by automated evidence extraction are explicitly marked for manual verification;
no performance value is inferred from a model mention.

| model | model_type | multilingual_or_vietnamese_specific | base_architecture | max_context_length_if_available | training_data_summary | task | dataset | domain | metric | performance | cost_or_compute | latency_if_available | strengths | weaknesses | citation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""
    rows = []
    for model, row in entries:
        if model == "Not automatically identified":
            family = "Not identified"
        elif model in {"PhoBERT"}:
            family = "Vietnamese-specific candidate"
        else:
            family = "Multilingual or baseline candidate; verify source"
        rows.append(
            f"| {model} | {row['model_type']} | {family} | Not extracted | Not extracted | Not extracted | "
            f"{row['task']} | {row['dataset'] or 'Not extracted'} | {row['domain']} | "
            f"{row['evaluation_metrics'] or 'Not extracted'} | Verify source result table | Not extracted | "
            f"Not extracted | Requires manual coding | Requires manual coding | [{row['citation_key']}; {row['paper_id']}] |"
        )
    (REPORTS_DIR / "model_comparison_table.md").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def escape_bib(value: str) -> str:
    return str(value).replace("{", "\\{").replace("}", "\\}")


def bibtex() -> None:
    core = read_csv(DATA_DIR / "core_papers.csv")
    matrix = read_csv(DATA_DIR / "literature_matrix.csv")
    keys = dict(zip(matrix["paper_id"], matrix["citation_key"]))
    entries = []
    for _, row in core.iterrows():
        key = keys.get(row["paper_id"], row["paper_id"])
        fields = [
            f"  title = {{{escape_bib(row['title'])}}}",
            f"  author = {{{escape_bib(authors_to_bibtex(row['authors']))}}}",
            f"  year = {{{row['year']}}}",
        ]
        if row["venue"]:
            fields.append(f"  howpublished = {{{escape_bib(row['venue'])}}}")
        if row["doi"]:
            fields.append(f"  doi = {{{row['doi']}}}")
        if row["url"]:
            fields.append(f"  url = {{{row['url']}}}")
        fields.append(f"  note = {{Pipeline paper ID: {row['paper_id']}}}")
        entries.append(f"@misc{{{key},\n" + ",\n".join(fields) + "\n}")
    (REFERENCES_DIR / "references.bib").write_text("\n\n".join(entries) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    if read_csv(DATA_DIR / "literature_matrix.csv").empty:
        raise FileNotFoundError("Run scripts/extract_literature_matrix.py before report generation.")
    prisma()
    literature_review()
    proposal()
    model_table()
    bibtex()
    print(f"Generated reports in {REPORTS_DIR} and BibTeX in {REFERENCES_DIR}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
