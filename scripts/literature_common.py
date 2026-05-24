"""Shared utilities for the Vietnamese retrieval literature-review pipeline."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse

import pandas as pd
import requests
from pydantic import BaseModel, ConfigDict, Field
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
PDF_DIR = ROOT / "papers" / "pdf"
REPORTS_DIR = ROOT / "reports"
REFERENCES_DIR = ROOT / "references"

SEARCH_STRINGS = [
    '("Vietnamese" AND "text embedding" AND "retrieval")',
    '("Vietnamese" AND "semantic search" AND "embedding")',
    '("Vietnamese" AND "information retrieval" AND "neural retrieval")',
    '("Vietnamese" AND "sentence embedding" AND "PhoBERT")',
    '("Vietnamese" AND "SBERT" AND "retrieval")',
    '("multilingual embedding" AND "Vietnamese" AND "retrieval")',
    '("BGE-M3" AND "Vietnamese" AND "retrieval")',
    '("multilingual-e5" AND "Vietnamese")',
    '("VN-MTEB" OR "Vietnamese Massive Text Embedding Benchmark")',
    '("MTEB" AND "Vietnamese" AND "embedding")',
    '("Vietnamese legal retrieval" OR "Vietnamese legal text retrieval")',
    '("Vietnamese medical retrieval" OR "Vietnamese biomedical retrieval")',
    '("Vietnamese news retrieval")',
    '("Vietnamese history" AND "retrieval" AND "embedding")',
    '("RAG" AND "Vietnamese" AND "embedding model")',
]

PAPER_COLUMNS = [
    "paper_id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "url",
    "pdf_url",
    "source_database",
    "abstract",
    "keywords",
    "citation_count",
    "open_access_status",
    "domain",
    "task_type",
    "models_mentioned",
    "datasets_mentioned",
    "metrics_mentioned",
    "relevance_score",
    "screening_status",
    "exclusion_reason",
]

DOWNLOAD_COLUMNS = [
    "paper_id",
    "title",
    "pdf_url",
    "download_status",
    "reason_if_failed",
    "file_path",
]

MATRIX_COLUMNS = [
    "paper_id",
    "citation_key",
    "research_problem",
    "model_type",
    "models_compared",
    "multilingual_models",
    "vietnamese_specific_models",
    "dataset",
    "domain",
    "task",
    "language",
    "evaluation_metrics",
    "best_result",
    "main_finding",
    "limitation",
    "relevance_to_our_topic",
    "possible_research_gap",
    "quote_or_evidence",
    "page_number_if_available",
]

MODEL_PATTERNS = {
    "BGE-M3": r"\bbge[- ]?m3\b",
    "multilingual-e5": r"\bmultilingual[- ]?e5\b|\bm[- ]?e5\b",
    "E5": r"\be5(?:[- ](?:base|large|small))?\b",
    "LaBSE": r"\blabse\b",
    "XLM-R": r"\bxlm[- ]?r(?:oberta)?\b",
    "PhoBERT": r"\bphobert\b",
    "Sentence-BERT": r"\bsentence[- ]?bert\b|\bsbert\b",
    "mBERT": r"\bmbert\b|multilingual bert",
    "DPR": r"\bdpr\b|dense passage retriev",
    "BM25": r"\bbm25\b",
    "Contriever": r"\bcontriever\b",
}

DATASET_PATTERNS = {
    "MTEB": r"\bmteb\b",
    "MMTEB": r"\bmmteb\b",
    "VN-MTEB": r"\bvn[- ]?mteb\b|vietnamese massive text embedding benchmark",
    "MIRACL": r"\bmiracl\b",
    "Mr. TyDi": r"\bmr\.?\s*tydi\b",
    "mMARCO": r"\bmmarco\b",
    "MLDR": r"\bmldr\b",
    "BEIR": r"\bbeir\b",
    "PhoMT": r"\bphomt\b",
    "ALQAC": r"\balqac\b",
}

METRIC_PATTERNS = {
    "nDCG": r"\bndcg(?:@\d+)?\b",
    "Recall": r"\brecall(?:@\d+)?\b",
    "MRR": r"\bmrr(?:@\d+)?\b|mean reciprocal rank",
    "MAP": r"\bmap(?:@\d+)?\b|mean average precision",
    "Hit@k": r"\bhit(?:s)?@\d+\b",
    "Accuracy": r"\baccuracy\b",
    "Precision": r"\bprecision(?:@\d+)?\b",
}


class PaperRecord(BaseModel):
    """Normalized public metadata for one candidate publication."""

    model_config = ConfigDict(extra="ignore")

    title: str
    authors: str = ""
    year: str = ""
    venue: str = ""
    doi: str = ""
    url: str = ""
    pdf_url: str = ""
    source_database: str
    abstract: str = ""
    keywords: str = ""
    citation_count: int | str = ""
    open_access_status: str = "unknown"
    external_ids: dict[str, str] = Field(default_factory=dict)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, CACHE_DIR, PDF_DIR, REPORTS_DIR, REFERENCES_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def compact_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(title: str) -> str:
    text = compact_text(title)
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_doi(doi: str) -> str:
    doi = compact_text(doi).lower()
    doi = re.sub(r"^(https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.strip()


def arxiv_id(text: str) -> str:
    match = re.search(r"(?:arxiv[:./ ]|abs/|pdf/)(\d{4}\.\d{4,5}(?:v\d+)?)", text, re.I)
    return re.sub(r"v\d+$", "", match.group(1)) if match else ""


def short_title(title: str, length: int = 58) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", normalize_title(title).title()).strip("_")
    return (cleaned or "paper")[:length].rstrip("_").lower()


def stable_paper_id(record: PaperRecord) -> str:
    key = normalize_doi(record.doi) or arxiv_id(f"{record.url} {record.pdf_url}")
    key = key or normalize_title(record.title)
    return "P" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10].upper()


def query_terms(query: str) -> str:
    text = re.sub(r"\b(?:AND|OR)\b", " ", query, flags=re.I)
    return re.sub(r'[()"]+', " ", text).strip()


def matched_items(text: str, patterns: dict[str, str]) -> str:
    hits = [name for name, pattern in patterns.items() if re.search(pattern, text, re.I)]
    return "; ".join(hits)


def classify_metadata(text: str) -> tuple[str, str, str, str]:
    domain_hits = []
    for label, terms in {
        "legal": r"\blegal\b|\blaw\b|\blegislat|\bcourt\b",
        "medical": r"\bmedical\b|\bhealth(?:care)?\b|\bbiomed|\bclinical\b",
        "news": r"\bnews\b|\bnewspaper\b",
        "history": r"\bhistory\b|\bhistorical\b",
    }.items():
        if re.search(terms, text, re.I):
            domain_hits.append(label)
    task_hits = []
    for label, terms in {
        "retrieval": r"\bretriev|\binformation retrieval\b|\bsearch\b",
        "embedding": r"\bembedding|\bsentence representation",
        "RAG": r"\bretrieval[- ]augmented\b|\brag\b",
        "benchmark": r"\bbenchmark|\bevaluat",
    }.items():
        if re.search(terms, text, re.I):
            task_hits.append(label)
    return (
        "; ".join(domain_hits) or "general",
        "; ".join(task_hits),
        matched_items(text, MODEL_PATTERNS),
        matched_items(text, DATASET_PATTERNS),
    )


class CachedClient:
    """Rate-limited GET client which persists successful responses verbatim."""

    def __init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update(
            {"User-Agent": os.getenv("LIT_REVIEW_USER_AGENT", "vn-retrieval-literature-review/1.0")}
        )
        self.delay = float(os.getenv("LIT_API_DELAY_SECONDS", "0.25"))
        self.last_request = 0.0

    def get(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 45,
    ) -> tuple[str, bool]:
        ensure_dirs()
        key = json.dumps([url, sorted((params or {}).items())], ensure_ascii=False)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        directory = CACHE_DIR / source.lower().replace(" ", "_")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{digest}.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload["body"], True
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        response = self.session.get(url, params=params, headers=headers, timeout=timeout)
        self.last_request = time.monotonic()
        response.raise_for_status()
        body = response.text
        path.write_text(
            json.dumps(
                {
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "url": response.url,
                    "status_code": response.status_code,
                    "body": body,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return body, False


def merge_records(records: Iterable[PaperRecord]) -> list[dict[str, Any]]:
    """Deduplicate using DOI, normalized title, arXiv id, and provider IDs."""

    merged: list[PaperRecord] = []
    identity_to_index: dict[str, int] = {}
    keyword_map: dict[int, set[str]] = {}
    year_priority_map: dict[int, int] = {}
    author_priority_map: dict[int, int] = {}
    doi_priority_map: dict[int, int] = {}

    def year_priority(source: str) -> int:
        priorities = {
            "ACL Anthology": 6,
            "Crossref": 5,
            "OpenAlex": 4,
            "Semantic Scholar": 3,
            "OpenReview": 2,
            "DBLP": 2,
            "arXiv": 1,
        }
        return max((priority for name, priority in priorities.items() if name in source), default=0)

    for record in records:
        record.title = compact_text(record.title)
        title_key = normalize_title(record.title)
        if not title_key:
            continue
        identities = {f"title:{title_key}"}
        if normalize_doi(record.doi):
            identities.add(f"doi:{normalize_doi(record.doi)}")
        candidate_arxiv = record.external_ids.get("ArXiv") or arxiv_id(
            f"{record.url} {record.pdf_url}"
        )
        if candidate_arxiv:
            clean_arxiv = re.sub(r"v\d+$", "", candidate_arxiv)
            identities.add(f"arxiv:{clean_arxiv}")
        for provider, value in record.external_ids.items():
            if value:
                identities.add(f"{provider.lower()}:{value.lower()}")
        existing = next((identity_to_index[x] for x in identities if x in identity_to_index), None)
        if existing is None:
            existing = len(merged)
            merged.append(record)
            keyword_map[existing] = set(filter(None, record.keywords.split("; ")))
            year_priority_map[existing] = year_priority(record.source_database)
            author_priority_map[existing] = year_priority(record.source_database)
            doi_priority_map[existing] = year_priority(record.source_database)
        else:
            base = merged[existing]
            sources = set(base.source_database.split("; ")) | set(record.source_database.split("; "))
            base.source_database = "; ".join(sorted(filter(None, sources)))
            keyword_map[existing].update(filter(None, record.keywords.split("; ")))
            for field in ("authors", "year", "venue", "doi", "url", "abstract"):
                incoming = getattr(record, field)
                current = getattr(base, field)
                if field == "year" and incoming and (
                    not current or year_priority(record.source_database) > year_priority_map[existing]
                ):
                    setattr(base, field, incoming)
                    year_priority_map[existing] = year_priority(record.source_database)
                elif field == "authors" and incoming and (
                    not current or year_priority(record.source_database) > author_priority_map[existing]
                ):
                    setattr(base, field, incoming)
                    author_priority_map[existing] = year_priority(record.source_database)
                elif field == "doi" and incoming and (
                    not current or year_priority(record.source_database) > doi_priority_map[existing]
                ):
                    setattr(base, field, incoming)
                    doi_priority_map[existing] = year_priority(record.source_database)
                elif (
                    field not in {"year", "authors", "doi"}
                    and incoming
                    and (not current or len(str(incoming)) > len(str(current)))
                ):
                    setattr(base, field, incoming)
            if record.pdf_url and not base.pdf_url:
                base.pdf_url = record.pdf_url
            if record.open_access_status == "open":
                base.open_access_status = "open"
                if record.pdf_url:
                    base.pdf_url = record.pdf_url
            counts = [c for c in (base.citation_count, record.citation_count) if str(c).isdigit()]
            base.citation_count = max(map(int, counts)) if counts else ""
            base.external_ids.update(record.external_ids)
        for identity in identities:
            identity_to_index[identity] = existing

    rows: list[dict[str, Any]] = []
    for index, record in enumerate(merged):
        normalized_doi = normalize_doi(record.doi)
        arxiv_doi = re.match(r"10\.48550/arxiv\.(.+)", normalized_doi, re.I)
        if arxiv_doi and not record.pdf_url:
            record.pdf_url = f"https://arxiv.org/pdf/{arxiv_doi.group(1)}"
            record.open_access_status = "open"
        combined = f"{record.title} {record.abstract} {' '.join(keyword_map[index])}"
        domain, task, models, datasets = classify_metadata(combined)
        rows.append(
            {
                "paper_id": stable_paper_id(record),
                "title": compact_text(record.title),
                "authors": record.authors,
                "year": record.year,
                "venue": record.venue,
                "doi": normalized_doi,
                "url": record.url,
                "pdf_url": record.pdf_url,
                "source_database": record.source_database,
                "abstract": record.abstract,
                "keywords": "; ".join(sorted(keyword_map[index])),
                "citation_count": record.citation_count,
                "open_access_status": record.open_access_status,
                "domain": domain,
                "task_type": task,
                "models_mentioned": models,
                "datasets_mentioned": datasets,
                "metrics_mentioned": matched_items(combined, METRIC_PATTERNS),
                "relevance_score": "",
                "screening_status": "unscreened",
                "exclusion_reason": "",
            }
        )
    return sorted(rows, key=lambda row: (str(row["year"]), row["title"]), reverse=True)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False) if path.exists() else pd.DataFrame()


def write_csv(path: Path, rows: Iterable[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows), columns=columns).to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def safe_pdf_url(row: pd.Series | dict[str, Any]) -> tuple[bool, str]:
    """Allow only API-asserted OA files or explicitly permitted repository hosts."""

    pdf_url = str(row.get("pdf_url", "")).strip()
    if not pdf_url:
        return False, "no open-access PDF URL in metadata"
    if str(row.get("open_access_status", "")).lower() != "open":
        return False, "metadata does not assert open access"
    sources = str(row.get("source_database", "")).lower()
    if any(name in sources for name in ("semantic scholar", "arxiv", "acl anthology", "openreview")):
        return True, "open-access URL supplied by permitted source"
    host = urlparse(pdf_url).netloc.lower()
    allowed_fragments = (
        "arxiv.org",
        "aclanthology.org",
        "openreview.net",
        "semanticscholar.org",
        "ncbi.nlm.nih.gov",
        "pmc.ncbi.nlm.nih.gov",
        "zenodo.org",
        "github.com",
        "raw.githubusercontent.com",
        "frontiersin.org",
        "mdpi.com",
        "springeropen.com",
    )
    if any(fragment in host for fragment in allowed_fragments):
        return True, "known open-access host"
    return False, "OA location host not in conservative download allowlist"


def authors_to_bibtex(authors: str) -> str:
    names = [compact_text(name) for name in authors.split(";") if compact_text(name)]
    return " and ".join(names)
