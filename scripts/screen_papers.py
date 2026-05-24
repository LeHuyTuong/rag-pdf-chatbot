"""Apply documented inclusion rules and rank candidate papers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
from tqdm import tqdm

from literature_common import (
    DATA_DIR,
    METRIC_PATTERNS,
    PAPER_COLUMNS,
    classify_metadata,
    matched_items,
    read_csv,
    write_csv,
)


def pdf_preview(path: str) -> str:
    if not path or not Path(path).exists():
        return ""
    try:
        with fitz.open(path) as document:
            return " ".join(page.get_text() for page in list(document)[:5])
    except Exception:
        return ""


def score_paper(
    row: pd.Series, evidence_text: str
) -> tuple[int, list[str], str, str, str, str, str, str, str]:
    metadata_text = " ".join(
        str(row.get(field, ""))
        for field in ("title", "abstract", "keywords", "domain", "task_type", "models_mentioned")
    )
    full = f"{metadata_text} {evidence_text}"
    retrieval = bool(
        re.search(
            r"\bretriev|\bsemantic search|\binformation retrieval|\bdense passage|"
            r"\bembedding|\bsentence representation|\bmteb\b|\brag\b",
            full,
            re.I,
        )
    )
    language = bool(
        re.search(
            r"\bvietnam|\bmultilingual|\bcross[- ]lingual|\blanguage[- ]agnostic|"
            r"\bphobert\b|\blabse\b|\bxlm[- ]?r|\bbge[- ]?m3|\bmultilingual[- ]?e5",
            full,
            re.I,
        )
    )
    metric_text = matched_items(full, METRIC_PATTERNS)
    method = bool(metric_text or re.search(r"\bbenchmark|\bevaluat|\bdataset|\bexperiment", full, re.I))
    no_metadata = not str(row.get("abstract", "")).strip() and not evidence_text
    title = str(row.get("title", ""))
    non_text_task = bool(
        re.search(
            r"\bimage[- ]text|\bvisual|\bvideo|\bmultimodal|\bspeech|\bvoice|\bmachine translation|"
            r"\bperson search|\bpedestrian|\bspeaker recognition|\bname(?:d)? entity|\bsentiment analysis|"
            r"\breading comprehension",
            title,
            re.I,
        )
        or (
            re.search(
                r"\bclassification|\bsummarization|\binformation extraction|\bparaphrase identification",
                title,
                re.I,
            )
            and not re.search(r"\bretriev|\bembedding benchmark|\bmteb\b|\brag\b", title, re.I)
        )
    )
    reasons = []
    score = 0
    direct_vietnamese = bool(
        re.search(r"\bvietnam", metadata_text, re.I)
        and re.search(r"\bretriev|\bembedding|\bsemantic search|\bmteb\b", metadata_text, re.I)
    )
    if direct_vietnamese:
        score += 3
        reasons.append("+3 directly addresses Vietnamese retrieval/embedding")
    models = [m.strip() for m in str(row.get("models_mentioned", "")).split(";") if m.strip()]
    if len(models) >= 2 or re.search(r"\bcompar|\bbaseline|versus|\bbenchmark", full, re.I):
        score += 2
        reasons.append("+2 includes comparative evaluation signals")
    if metric_text:
        score += 2
        reasons.append("+2 retrieval/evaluation metrics detected")
    domain, _, _, _ = classify_metadata(metadata_text)
    _, task, found_models, datasets = classify_metadata(full)
    if domain != "general":
        score += 1
        reasons.append("+1 target-domain terminology detected")
    if re.search(r"\bcode\b|\brepository|\bgithub|\brelease|\bdataset|\bbenchmark|\bmodel", full, re.I):
        score += 1
        reasons.append("+1 reusable model/data/code signal detected")
    try:
        if int(float(str(row.get("year", "0")) or 0)) >= 2022:
            score += 1
            reasons.append("+1 published in or after 2022")
    except ValueError:
        pass
    if not (retrieval and language):
        score -= 2
        reasons.append("-2 only loosely related to Vietnamese/multilingual retrieval scope")
    if not method:
        score -= 3
        reasons.append("-3 no usable method/metric signal in available metadata/text")
    score = max(0, min(10, score))
    if non_text_task:
        decision = "exclude"
        exclusion = "Non-text or multimodal/translation/classification task outside text retrieval scope."
    elif no_metadata and len(str(row.get("title", ""))) < 10:
        decision = "exclude"
        exclusion = "No abstract or accessible usable metadata."
    elif not retrieval:
        decision = "exclude"
        exclusion = "Not related to embeddings or retrieval in available metadata/full text."
    elif not language:
        decision = "exclude"
        exclusion = "No Vietnamese or multilingual relevance detected."
    elif not method:
        decision = "peripheral"
        exclusion = "Retrieval/embedding relevance found, but no evaluative methodology or metrics located."
    else:
        decision = "eligible"
        exclusion = ""
    return score, reasons, decision, exclusion, domain, task, found_models, datasets, metric_text


def main() -> int:
    papers = read_csv(DATA_DIR / "papers_raw.csv")
    downloads = read_csv(DATA_DIR / "pdf_download_log.csv")
    if papers.empty:
        raise FileNotFoundError("Run scripts/search_papers.py before screening.")
    download_paths = (
        dict(zip(downloads["paper_id"], downloads["file_path"])) if not downloads.empty else {}
    )
    scored: list[dict[str, Any]] = []
    for _, row in tqdm(papers.iterrows(), total=len(papers), desc="Screening records"):
        preview = pdf_preview(download_paths.get(row["paper_id"], ""))
        score, reasons, decision, exclusion, domain, task, models, datasets, metrics = score_paper(
            row, preview
        )
        item = row.to_dict()
        item.update(
            {
                "domain": domain,
                "task_type": task,
                "models_mentioned": models,
                "datasets_mentioned": datasets,
                "metrics_mentioned": metrics,
                "relevance_score": score,
                "screening_status": decision,
                "exclusion_reason": exclusion or " | ".join(reasons),
                "_has_pdf": bool(download_paths.get(row["paper_id"], "")),
                "_direct": bool(
                    re.search(r"\bvietnam", f"{row.get('title', '')} {row.get('abstract', '')}", re.I)
                    and re.search(
                        r"\bretriev|\bembedding|\bsemantic search|\bmteb\b",
                        f"{row.get('title', '')} {row.get('abstract', '')}",
                        re.I,
                    )
                ),
                "_focus": bool(
                    re.search(
                        r"\bretriev|\binformation retrieval|\bembedding|\bmteb\b|\bsemantic search|\brerank",
                        str(row.get("title", "")),
                        re.I,
                    )
                ),
                "_background": bool(
                    re.search(
                        r"\bmmteb\b|\bmultilingual e5\b|\bmGTE\b|\bjina-embeddings\b|\bNLLB-E5\b|"
                        r"\bLaBSE\b|\bXLM-R\b|\bBGE-M3\b",
                        str(row.get("title", "")),
                        re.I,
                    )
                ),
            }
        )
        scored.append(item)
    ranked = sorted(
        [r for r in scored if r["screening_status"] == "eligible"],
        key=lambda r: (
            r["_direct"],
            r["_focus"],
            r["_has_pdf"],
            int(r["relevance_score"]),
            int(r["citation_count"] or 0),
        ),
        reverse=True,
    )
    base_count = min(11, len(ranked))
    target_core_count = min(15, len(ranked)) if len(ranked) >= 10 else len(ranked)
    core_ids = {r["paper_id"] for r in ranked[:base_count]}
    for domain in ("medical", "history", "news"):
        if any(domain in str(r["domain"]).lower() for r in ranked if r["paper_id"] in core_ids):
            continue
        domain_candidate = next(
            (
                r
                for r in ranked
                if domain in str(r["domain"]).lower()
                and r["_direct"]
                and r["_focus"]
                and r["paper_id"] not in core_ids
            ),
            None,
        )
        if domain_candidate and len(core_ids) < target_core_count:
            core_ids.add(domain_candidate["paper_id"])
    background_for_core = sorted(
        [r for r in ranked if r["_background"] and r["paper_id"] not in core_ids],
        key=lambda r: (r["_has_pdf"], int(r["relevance_score"]), int(r["citation_count"] or 0)),
        reverse=True,
    )
    for row in background_for_core:
        if len(core_ids) >= target_core_count:
            break
        core_ids.add(row["paper_id"])
    for row in ranked:
        if len(core_ids) >= target_core_count:
            break
        core_ids.add(row["paper_id"])
    support_ranked = sorted(
        [r for r in ranked if r["paper_id"] not in core_ids],
        key=lambda r: (
            r["_background"],
            r["_direct"],
            r["_has_pdf"],
            int(r["relevance_score"]),
            int(r["citation_count"] or 0),
        ),
        reverse=True,
    )
    support_ids = {r["paper_id"] for r in support_ranked[:20]}
    for row in scored:
        if row["paper_id"] in core_ids:
            row["screening_status"] = "core"
        elif row["paper_id"] in support_ids:
            row["screening_status"] = "supporting"
        elif row["screening_status"] == "eligible":
            row["screening_status"] = "peripheral"
            row["exclusion_reason"] = "Eligible but outside highest ranked core/supporting set."
    clean = [{column: row.get(column, "") for column in PAPER_COLUMNS} for row in scored]
    write_csv(DATA_DIR / "screened_papers.csv", clean, PAPER_COLUMNS)
    write_csv(DATA_DIR / "core_papers.csv", [r for r in clean if r["screening_status"] == "core"], PAPER_COLUMNS)
    write_csv(
        DATA_DIR / "supporting_papers.csv",
        [r for r in clean if r["screening_status"] == "supporting"],
        PAPER_COLUMNS,
    )
    write_csv(
        DATA_DIR / "excluded_papers.csv",
        [r for r in clean if r["screening_status"] in {"exclude", "peripheral"}],
        PAPER_COLUMNS,
    )
    print(
        f"Screened {len(clean)} unique records: {len(core_ids)} core, "
        f"{len(support_ids)} supporting, {len(clean) - len(core_ids) - len(support_ids)} excluded/peripheral."
    )
    return 0 if len(core_ids) >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
