"""Download only PDFs supported by open-access metadata or allowed OA hosts."""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from literature_common import (
    DATA_DIR,
    DOWNLOAD_COLUMNS,
    PDF_DIR,
    ensure_dirs,
    read_csv,
    safe_pdf_url,
    short_title,
    write_csv,
)


def session() -> requests.Session:
    http = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504))
    http.mount("https://", HTTPAdapter(max_retries=retry))
    http.headers["User-Agent"] = os.getenv(
        "LIT_REVIEW_USER_AGENT", "vn-retrieval-literature-review/1.0"
    )
    return http


def in_review_scope(row: pd.Series) -> bool:
    """Keep downloads focused on evidence present in publication metadata."""

    text = " ".join(
        str(row.get(field, ""))
        for field in ("title", "abstract", "models_mentioned", "datasets_mentioned", "task_type")
    )
    language = re.search(
        r"\bvietnam|\bmultilingual|\bcross[- ]lingual|\blanguage[- ]agnostic|"
        r"\bphobert\b|\blabse\b|\bxlm[- ]?r|\bbge[- ]?m3|\bmultilingual[- ]?e5|\bmmteb\b",
        text,
        re.I,
    )
    retrieval = re.search(
        r"\bretriev|\bembedding|\bsemantic search|\binformation retrieval|\bmteb\b|\brag\b",
        text,
        re.I,
    )
    title = str(row.get("title", ""))
    non_text_task = re.search(
        r"\bimage[- ]text|\bvisual|\bvideo|\bmultimodal|\bspeech|\bvoice|\bmachine translation|"
        r"\bperson search|\bpedestrian|\bspeaker recognition|\bname(?:d)? entity|\bsentiment analysis|"
        r"\breading comprehension",
        title,
        re.I,
    ) or (
        re.search(r"\bclassification|\bsummarization|\binformation extraction|\bparaphrase identification", title, re.I)
        and not re.search(r"\bretriev|\bembedding benchmark|\bmteb\b|\brag\b", title, re.I)
    )
    return bool(language and retrieval and not non_text_task)


def main() -> int:
    ensure_dirs()
    papers = read_csv(DATA_DIR / "papers_raw.csv")
    if papers.empty:
        raise FileNotFoundError("Run scripts/search_papers.py before downloading PDFs.")
    http = session()
    delay = float(os.getenv("LIT_PDF_DELAY_SECONDS", "0.35"))
    maximum = int(os.getenv("LIT_MAX_PDFS", "80"))
    downloaded = 0
    logs: list[dict[str, str]] = []
    papers = papers.assign(
        _scope=papers.apply(in_review_scope, axis=1),
        _direct=papers.apply(
            lambda row: bool(re.search(r"\bvietnam", f"{row['title']} {row['abstract']}", re.I)), axis=1
        ),
    ).sort_values(["_scope", "_direct", "year"], ascending=[False, False, False])
    for _, row in tqdm(papers.iterrows(), total=len(papers), desc="Downloading permitted PDFs"):
        allowed, reason = safe_pdf_url(row)
        destination = PDF_DIR / f"{row['paper_id']}_{short_title(row['title'])}.pdf"
        log = {
            "paper_id": row["paper_id"],
            "title": row["title"],
            "pdf_url": row["pdf_url"],
            "download_status": "not_downloaded",
            "reason_if_failed": reason,
            "file_path": "",
        }
        if allowed and not row["_scope"]:
            log["reason_if_failed"] = "publication metadata does not indicate scoped multilingual/Vietnamese retrieval relevance"
            logs.append(log)
            continue
        if not allowed:
            logs.append(log)
            continue
        if destination.exists() and destination.stat().st_size > 1000:
            log.update(download_status="downloaded", reason_if_failed="", file_path=str(destination))
            logs.append(log)
            downloaded += 1
            continue
        if downloaded >= maximum:
            log["reason_if_failed"] = "download cap reached; raise LIT_MAX_PDFS to retrieve"
            logs.append(log)
            continue
        try:
            time.sleep(delay)
            response = http.get(row["pdf_url"], timeout=60, allow_redirects=True)
            response.raise_for_status()
            content = response.content
            if not content.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            destination.write_bytes(content)
            log.update(download_status="downloaded", reason_if_failed="", file_path=str(destination))
            downloaded += 1
        except Exception as exc:
            log["download_status"] = "failed"
            log["reason_if_failed"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        logs.append(log)
    write_csv(DATA_DIR / "pdf_download_log.csv", logs, DOWNLOAD_COLUMNS)
    print(f"Downloaded/reused {downloaded} open-access PDFs into {PDF_DIR}.")
    return 0 if downloaded >= 20 else 1


if __name__ == "__main__":
    sys.exit(main())
