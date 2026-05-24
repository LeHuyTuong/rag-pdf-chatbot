"""Extract constrained, traceable evidence excerpts from selected core papers."""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import fitz
from tqdm import tqdm

from literature_common import DATA_DIR, MATRIX_COLUMNS, read_csv, write_csv


EVIDENCE_TERMS = re.compile(
    r"retriev|embedding|ndcg|recall|mrr|mean reciprocal|map|benchmark|vietnam|multilingual",
    re.I,
)
METRIC_TERMS = re.compile(r"\bndcg(?:@\d+)?\b|\brecall(?:@\d+)?\b|\bmrr(?:@\d+)?\b|\bmap(?:@\d+)?\b", re.I)
RESULT_TERMS = re.compile(r"\bevaluat|\bexperiment|\bbenchmark|\bresult|\boutperform|\bimprov|\bachiev", re.I)


def citation_key(row: dict[str, Any]) -> str:
    first_author = str(row.get("authors", "")).split(";")[0].strip()
    surname_text = first_author.split()[-1] if first_author else ""
    surname_text = surname_text.replace("Đ", "D").replace("đ", "d")
    surname = re.sub(
        r"[^A-Za-z]", "", unicodedata.normalize("NFKD", surname_text).encode("ascii", "ignore").decode()
    )
    if not surname:
        surname = "Unknown"
    year = str(row.get("year", "") or "nd")
    return f"{surname}{year}_{row['paper_id']}"


def excerpt(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    candidates = []
    for sentence in re.split(r"(?<=[.!?])\s+", clean):
        if len(sentence.split()) < 8 or not EVIDENCE_TERMS.search(sentence):
            continue
        score = 5 * bool(METRIC_TERMS.search(sentence)) + 2 * bool(RESULT_TERMS.search(sentence))
        score += bool(re.search(r"\bvietnam", sentence, re.I))
        candidates.append((score, sentence))
    chosen = max(candidates, default=(0, clean), key=lambda item: item[0])[1]
    words = chosen.split()
    if len(words) > 24:
        trigger = next(
            (index for index, word in enumerate(words) if METRIC_TERMS.search(word) or RESULT_TERMS.search(word)),
            0,
        )
        start = max(0, trigger - 8)
        return ("... " if start else "") + " ".join(words[start : start + 24]) + " ..."
    if words:
        return " ".join(words)
    return ""


def extract_pdf_evidence(path: str) -> tuple[str, str]:
    if not path or not Path(path).exists():
        return "", ""
    try:
        with fitz.open(path) as document:
            best = (0, "", "")
            for page_number, page in enumerate(document, start=1):
                text = page.get_text()
                if EVIDENCE_TERMS.search(text):
                    evidence = excerpt(text)
                    score = 5 * bool(METRIC_TERMS.search(evidence)) + 2 * bool(RESULT_TERMS.search(evidence))
                    if score > best[0] or not best[1]:
                        best = (score, evidence, str(page_number))
            if best[1]:
                return best[1], best[2]
    except Exception:
        return "", ""
    return "", ""


def main() -> int:
    core = read_csv(DATA_DIR / "core_papers.csv")
    downloads = read_csv(DATA_DIR / "pdf_download_log.csv")
    if core.empty:
        raise FileNotFoundError("Run scripts/screen_papers.py and select core papers first.")
    paths = dict(zip(downloads["paper_id"], downloads["file_path"])) if not downloads.empty else {}
    rows = []
    for _, paper in tqdm(core.iterrows(), total=len(core), desc="Extracting evidence"):
        data = paper.to_dict()
        evidence, page = extract_pdf_evidence(paths.get(data["paper_id"], ""))
        evidence_source = "PDF evidence excerpt"
        if not evidence:
            evidence = excerpt(data.get("abstract", ""))
            evidence_source = "Abstract evidence excerpt"
        language = "Vietnamese" if re.search(r"\bvietnam", f"{data['title']} {data['abstract']}", re.I) else "Multilingual"
        multi = "; ".join(
            model
            for model in str(data.get("models_mentioned", "")).split("; ")
            if model in {"BGE-M3", "multilingual-e5", "E5", "LaBSE", "XLM-R", "mBERT"}
        )
        vi_model = "; ".join(
            model
            for model in str(data.get("models_mentioned", "")).split("; ")
            if model in {"PhoBERT"}
        )
        raw_models = data.get("models_mentioned", "")
        raw_dataset = data.get("datasets_mentioned", "")
        raw_metrics = data.get("metrics_mentioned", "")
        rows.append(
            {
                "paper_id": data["paper_id"],
                "citation_key": citation_key(data),
                "research_problem": data.get("title", ""),
                "model_type": data.get("task_type", ""),
                "models_compared": (
                    f"Detected terms only; verify comparison: {raw_models}"
                    if raw_models
                    else "Not automatically coded."
                ),
                "multilingual_models": (
                    f"Detected terms only: {multi}" if multi else "Not automatically identified."
                ),
                "vietnamese_specific_models": (
                    f"Detected terms only: {vi_model}" if vi_model else "Not automatically identified."
                ),
                "dataset": (
                    f"Detected terms only; verify use: {raw_dataset}"
                    if raw_dataset
                    else "Not automatically identified."
                ),
                "domain": data.get("domain", ""),
                "task": data.get("task_type", ""),
                "language": language,
                "evaluation_metrics": (
                    f"Detected terms only; verify definitions/values: {raw_metrics}"
                    if raw_metrics
                    else "Not automatically identified."
                ),
                "best_result": "Not automatically coded; verify result tables in full text.",
                "main_finding": "Not automatically synthesized; use the traceable evidence excerpt for manual coding.",
                "limitation": "Automated extraction records evidence terms but does not infer comparative conclusions.",
                "relevance_to_our_topic": (
                    "Selected during screening for Vietnamese/multilingual embedding or retrieval relevance; "
                    f"score={data.get('relevance_score', '')}/10."
                ),
                "possible_research_gap": (
                    "Check whether this source directly compares multilingual and Vietnamese-specific "
                    "embeddings on matched domain retrieval data."
                ),
                "quote_or_evidence": f"{evidence_source} (<=24 words): {evidence}",
                "page_number_if_available": page,
            }
        )
    write_csv(DATA_DIR / "literature_matrix.csv", rows, MATRIX_COLUMNS)
    print(f"Wrote {len(rows)} source-linked evidence records to {DATA_DIR / 'literature_matrix.csv'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
