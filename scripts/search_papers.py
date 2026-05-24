"""Collect and deduplicate literature metadata from public scholarly APIs."""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from literature_common import (
    CACHE_DIR,
    DATA_DIR,
    PAPER_COLUMNS,
    ROOT,
    SEARCH_STRINGS,
    CachedClient,
    PaperRecord,
    compact_text,
    ensure_dirs,
    merge_records,
    query_terms,
    write_csv,
)


RESULTS_PER_QUERY = int(os.getenv("LIT_RESULTS_PER_QUERY", "10"))
client = CachedClient()
dblp_client = CachedClient()
dblp_client.session.mount("https://", HTTPAdapter(max_retries=Retry(total=0)))
search_log: list[dict[str, Any]] = []


def note(source: str, query: str, count: int, status: str, cached: bool = False) -> None:
    search_log.append(
        {
            "searched_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_database": source,
            "search_string": query,
            "records_returned": count,
            "status": status,
            "from_cache": cached,
        }
    )


def try_json(source: str, query: str, url: str, params: dict[str, Any], headers=None) -> tuple[Any, bool]:
    try:
        body, cached = client.get(source, url, params=params, headers=headers)
        return json.loads(body), cached
    except Exception as exc:
        note(source, query, 0, f"failed: {type(exc).__name__}: {str(exc)[:120]}")
        return None, False


def semantic_scholar(query: str) -> list[PaperRecord]:
    source = "Semantic Scholar"
    headers = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
    payload, cached = try_json(
        source,
        query,
        "https://api.semanticscholar.org/graph/v1/paper/search",
        {
            "query": query_terms(query),
            "limit": RESULTS_PER_QUERY,
            "fields": "paperId,title,authors,year,venue,abstract,citationCount,externalIds,url,openAccessPdf",
        },
        headers,
    )
    if payload is None:
        return []
    records = []
    for item in payload.get("data", []):
        oa = item.get("openAccessPdf") or {}
        external = item.get("externalIds") or {}
        external["SemanticScholar"] = item.get("paperId", "")
        records.append(
            PaperRecord(
                title=item.get("title") or "",
                authors="; ".join(a.get("name", "") for a in item.get("authors", [])),
                year=str(item.get("year") or ""),
                venue=item.get("venue") or "",
                doi=external.get("DOI", ""),
                url=item.get("url") or "",
                pdf_url=oa.get("url") or "",
                source_database=source,
                abstract=compact_text(item.get("abstract")),
                keywords="",
                citation_count=item.get("citationCount", ""),
                open_access_status="open" if oa.get("url") else "unknown",
                external_ids={str(k): str(v) for k, v in external.items() if v},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def crossref(query: str) -> list[PaperRecord]:
    source = "Crossref"
    params = {
        "query.bibliographic": query_terms(query),
        "rows": RESULTS_PER_QUERY,
        "select": "DOI,title,author,published,container-title,URL,abstract,is-referenced-by-count,subject,type",
    }
    if os.getenv("CROSSREF_MAILTO"):
        params["mailto"] = os.environ["CROSSREF_MAILTO"]
    payload, cached = try_json(source, query, "https://api.crossref.org/works", params)
    if payload is None:
        return []
    records = []
    for item in payload.get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0]
        if not title:
            continue
        date_parts = item.get("published", {}).get("date-parts", [[]])
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
        authors = "; ".join(
            compact_text(f"{a.get('given', '')} {a.get('family', '')}") for a in item.get("author", [])
        )
        records.append(
            PaperRecord(
                title=title,
                authors=authors,
                year=year,
                venue=(item.get("container-title") or [""])[0],
                doi=item.get("DOI", ""),
                url=item.get("URL", ""),
                source_database=source,
                abstract=compact_text(item.get("abstract")),
                keywords="; ".join(item.get("subject") or []),
                citation_count=item.get("is-referenced-by-count", ""),
                external_ids={"DOI": item.get("DOI", "")},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def openalex(query: str) -> list[PaperRecord]:
    source = "OpenAlex"
    params: dict[str, Any] = {"search": query_terms(query), "per-page": RESULTS_PER_QUERY}
    if os.getenv("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    payload, cached = try_json(source, query, "https://api.openalex.org/works", params)
    if payload is None:
        return []
    records = []
    for item in payload.get("results", []):
        index = item.get("abstract_inverted_index") or {}
        positioned = [(position, word) for word, positions in index.items() for position in positions]
        abstract = " ".join(word for _, word in sorted(positioned))
        oa = item.get("open_access") or {}
        location = item.get("best_oa_location") or {}
        primary_location = item.get("primary_location") or {}
        primary_source = primary_location.get("source") or {}
        ids = item.get("ids") or {}
        records.append(
            PaperRecord(
                title=item.get("title") or "",
                authors="; ".join(
                    a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])
                ),
                year=str(item.get("publication_year") or ""),
                venue=primary_source.get("display_name", "") or "",
                doi=ids.get("doi", ""),
                url=ids.get("doi") or item.get("id", ""),
                pdf_url=location.get("pdf_url") or "",
                source_database=source,
                abstract=compact_text(abstract),
                keywords="",
                citation_count=item.get("cited_by_count", ""),
                open_access_status="open" if oa.get("is_oa") and location.get("pdf_url") else "unknown",
                external_ids={"OpenAlex": item.get("id", ""), "DOI": ids.get("doi", "")},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def arxiv(query: str) -> list[PaperRecord]:
    source = "arXiv"
    try:
        body, cached = client.get(
            source,
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query_terms(query)}",
                "start": 0,
                "max_results": RESULTS_PER_QUERY,
            },
        )
        root = ET.fromstring(body)
    except Exception as exc:
        note(source, query, 0, f"failed: {type(exc).__name__}: {str(exc)[:120]}")
        return []
    atom = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    records = []
    for entry in root.findall("a:entry", atom):
        entry_url = entry.findtext("a:id", default="", namespaces=atom)
        pdf_url = ""
        for link in entry.findall("a:link", atom):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
        records.append(
            PaperRecord(
                title=compact_text(entry.findtext("a:title", default="", namespaces=atom)),
                authors="; ".join(
                    compact_text(a.findtext("a:name", default="", namespaces=atom))
                    for a in entry.findall("a:author", atom)
                ),
                year=entry.findtext("a:published", default="", namespaces=atom)[:4],
                venue="arXiv",
                doi=entry.findtext("arxiv:doi", default="", namespaces=atom),
                url=entry_url,
                pdf_url=pdf_url,
                source_database=source,
                abstract=compact_text(entry.findtext("a:summary", default="", namespaces=atom)),
                keywords="",
                open_access_status="open",
                external_ids={"ArXiv": entry_url.rsplit("/", 1)[-1]},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def dblp(query: str) -> list[PaperRecord]:
    source = "DBLP"
    try:
        body, cached = dblp_client.get(
            source,
            "https://dblp.org/search/publ/api",
            params={"q": query_terms(query), "format": "json", "h": RESULTS_PER_QUERY},
            timeout=float(os.getenv("LIT_DBLP_TIMEOUT_SECONDS", "4")),
        )
        payload = json.loads(body)
    except Exception as exc:
        note(source, query, 0, f"failed: {type(exc).__name__}: {str(exc)[:120]}")
        return []
    hits = payload.get("result", {}).get("hits", {}).get("hit", [])
    records = []
    for hit in hits:
        item = hit.get("info", {})
        authors_raw = item.get("authors", {}).get("author", [])
        if isinstance(authors_raw, dict):
            authors_raw = [authors_raw]
        records.append(
            PaperRecord(
                title=compact_text(item.get("title")),
                authors="; ".join(a.get("text", "") if isinstance(a, dict) else a for a in authors_raw),
                year=str(item.get("year", "")),
                venue=item.get("venue", ""),
                doi=item.get("doi", ""),
                url=item.get("url", ""),
                source_database=source,
                keywords="",
                open_access_status="unknown",
                external_ids={"DBLP": item.get("key", ""), "DOI": item.get("doi", "")},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def openreview(query: str) -> list[PaperRecord]:
    source = "OpenReview"
    payload, cached = try_json(
        source,
        query,
        "https://api2.openreview.net/notes/search",
        {"query": query_terms(query), "limit": RESULTS_PER_QUERY},
    )
    if payload is None:
        return []
    records = []
    for item in payload.get("notes", []):
        content = item.get("content") or {}

        def value(key: str) -> Any:
            candidate = content.get(key, "")
            return candidate.get("value", "") if isinstance(candidate, dict) else candidate

        title = value("title")
        if not title:
            continue
        authors = value("authors") or []
        timestamp = item.get("cdate")
        year = (
            datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc).strftime("%Y")
            if timestamp
            else ""
        )
        pdf = value("pdf")
        pdf_url = f"https://openreview.net{pdf}" if str(pdf).startswith("/") else str(pdf)
        records.append(
            PaperRecord(
                title=str(title),
                authors="; ".join(authors) if isinstance(authors, list) else str(authors),
                year=year,
                venue=value("venue") or "OpenReview",
                url=f"https://openreview.net/forum?id={item.get('id', '')}",
                pdf_url=pdf_url,
                source_database=source,
                abstract=compact_text(value("abstract")),
                keywords="",
                open_access_status="open" if pdf_url else "unknown",
                external_ids={"OpenReview": item.get("id", "")},
            )
        )
    note(source, query, len(records), "ok", cached)
    return records


def acl_anthology(query: str) -> list[PaperRecord]:
    """Use ACL's official search results and citation metadata when returned."""

    source = "ACL Anthology"
    try:
        body, cached = client.get(
            source, "https://aclanthology.org/search/", params={"q": query_terms(query)}
        )
    except Exception as exc:
        note(source, query, 0, f"failed: {type(exc).__name__}: {str(exc)[:120]}")
        return []
    ids = list(dict.fromkeys(re.findall(r'href="/([A-Z0-9][^"/]+(?:\.[0-9]+)?)/"', body)))[:RESULTS_PER_QUERY]
    records = []
    for anthology_id in ids:
        try:
            page, _ = client.get(source, f"https://aclanthology.org/{anthology_id}/")
            metas = dict(re.findall(r'<meta name="([^"]+)" content="([^"]*)"', page))
            if not metas.get("citation_title"):
                continue
            records.append(
                PaperRecord(
                    title=compact_text(metas.get("citation_title")),
                    authors=metas.get("citation_author", ""),
                    year=metas.get("citation_publication_date", "")[:4],
                    venue=metas.get("citation_conference_title", "ACL Anthology"),
                    doi=metas.get("citation_doi", ""),
                    url=f"https://aclanthology.org/{anthology_id}/",
                    pdf_url=metas.get("citation_pdf_url", ""),
                    source_database=source,
                    keywords="",
                    open_access_status="open" if metas.get("citation_pdf_url") else "unknown",
                    external_ids={"ACL": anthology_id},
                )
            )
        except Exception:
            continue
    note(source, query, len(records), "ok", cached)
    return records


def huggingface_supporting_sources() -> None:
    source = "Hugging Face model cards"
    rows = []
    for query in ("BGE-M3", "multilingual-e5", "Vietnamese embedding", "PhoBERT sentence embedding"):
        payload, cached = try_json(
            source,
            query,
            "https://huggingface.co/api/models",
            {"search": query, "limit": 10, "full": "false"},
        )
        if payload is None:
            continue
        for item in payload:
            model_id = item.get("id") or item.get("modelId", "")
            rows.append(
                {
                    "source_type": "supporting model card",
                    "model_id": model_id,
                    "url": f"https://huggingface.co/{model_id}",
                    "matched_query": query,
                    "last_modified": item.get("lastModified", ""),
                }
            )
        note(source, query, len(payload), "ok", cached)
    pd.DataFrame(rows).drop_duplicates(subset=["model_id"]).to_csv(
        DATA_DIR / "huggingface_model_sources.csv", index=False
    )


def write_manual_google_scholar_queries() -> None:
    lines = [
        "# Google Scholar Manual Search Protocol",
        "",
        "Google Scholar is intentionally not scraped by this pipeline. Run these exact searches manually,",
        "export permitted citation metadata, and record any newly screened items in `data/papers_raw.csv`",
        "with `source_database=Google Scholar (manual)` before rerunning downstream stages.",
        "",
    ]
    lines.extend(f"- `{query}`" for query in SEARCH_STRINGS)
    (DATA_DIR / "google_scholar_manual_queries.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    records: list[PaperRecord] = []
    adapters = [
        semantic_scholar,
        crossref,
        openalex,
        arxiv,
        acl_anthology,
        openreview,
        dblp,
    ]
    for adapter in adapters:
        for query in tqdm(SEARCH_STRINGS, desc=f"Searching {adapter.__name__}"):
            try:
                records.extend(adapter(query))
            except Exception as exc:
                note(adapter.__name__, query, 0, f"parser failed: {type(exc).__name__}: {str(exc)[:120]}")
    huggingface_supporting_sources()
    write_manual_google_scholar_queries()
    rows = merge_records(records)
    write_csv(DATA_DIR / "papers_raw.csv", rows, PAPER_COLUMNS)
    pd.DataFrame(search_log).to_csv(DATA_DIR / "search_log.csv", index=False)
    print(f"Collected {len(records)} records; retained {len(rows)} unique candidate papers.")
    print(f"Metadata: {DATA_DIR / 'papers_raw.csv'}")
    return 0 if len(rows) >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
