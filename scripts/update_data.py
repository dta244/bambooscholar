"""
BambooScholar — OpenAlex Data Updater
Fetches Vietnamese-affiliated publication and citation data from OpenAlex API.
Outputs JSON files to data/ for the static dashboard.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://api.openalex.org"
HEADERS = {"User-Agent": "BambooScholar/1.0 (tpduong.vie@gmail.com)"}
API_KEY = os.environ.get("OPENALEX_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
VN_FILTER = "authorships.institutions.country_code:VN"
TOP_INSTITUTIONS_LIMIT = 50
TOP_CITED_LIMIT = 25
YEAR_START = 2000

# --- HTTP session with retry ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))


def get(url, params=None):
    """Make a GET request to OpenAlex with rate-limit awareness."""
    if params is None:
        params = {}
    if API_KEY:
        params["api_key"] = API_KEY
    r = session.get(url, headers=HEADERS, params=params)
    remaining = r.headers.get("X-RateLimit-Remaining")
    if remaining and int(remaining) < 5:
        print(f"  Rate limit low ({remaining} remaining), sleeping 2s...")
        time.sleep(2)
    r.raise_for_status()
    time.sleep(0.1)
    return r.json()


def cursor_paginate_sum(base_url, extra_params=None, max_pages=0):
    """Use cursor pagination to sum cited_by_count across all results.

    Args:
        max_pages: Maximum pages to fetch. 0 = unlimited (full pagination).
    """
    total_citations = 0
    total_works = 0
    params = {"cursor": "*", "per-page": "200", "select": "id,cited_by_count"}
    if extra_params:
        params.update(extra_params)

    url = base_url
    cursor = "*"
    page = 0

    while cursor:
        params["cursor"] = cursor
        data = get(url, params)
        results = data.get("results", [])
        if not results:
            break
        for work in results:
            total_citations += work.get("cited_by_count", 0)
            total_works += 1
        cursor = data.get("meta", {}).get("next_cursor")
        page += 1
        if max_pages and page >= max_pages:
            # Estimate remaining citations based on sampled average
            total_in_set = data.get("meta", {}).get("count", total_works)
            if total_works > 0 and total_in_set > total_works:
                avg_per_work = total_citations / total_works
                total_citations = int(avg_per_work * total_in_set)
                total_works = total_in_set
            break
        if page % 50 == 0:
            print(f"    Paginated {page} pages, {total_works} works so far...")

    return total_citations, total_works


def save_json(filename, data):
    """Write JSON to data/ directory."""
    path = os.path.join(DATA_DIR, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved {path}")


def fetch_total_count():
    """A. Total Vietnam-affiliated publications."""
    print("1. Fetching total publication count...")
    data = get(f"{BASE}/works", {"filter": VN_FILTER})
    count = data["meta"]["count"]
    print(f"   Total papers: {count:,}")
    return count


def fetch_by_field():
    """B. Publications grouped by field."""
    print("2. Fetching publications by field...")
    data = get(f"{BASE}/works", {"filter": VN_FILTER, "group_by": "primary_topic.field.id"})
    fields = []
    for bucket in data.get("group_by", []):
        fields.append({
            "field_id": bucket["key"],
            "field_name": bucket["key_display_name"],
            "paper_count": bucket["count"],
        })
    fields.sort(key=lambda x: x["paper_count"], reverse=True)
    print(f"   Found {len(fields)} fields")
    return fields


def fetch_by_institution():
    """C. Publications grouped by institution."""
    print("3. Fetching publications by institution...")
    data = get(f"{BASE}/works", {"filter": VN_FILTER, "group_by": "institutions.id"})
    institutions = []
    for bucket in data.get("group_by", []):
        if bucket["key"] == "unknown":
            continue
        institutions.append({
            "institution_id": bucket["key"],
            "institution_name": bucket["key_display_name"],
            "paper_count": bucket["count"],
        })
    institutions.sort(key=lambda x: x["paper_count"], reverse=True)
    institutions = institutions[:TOP_INSTITUTIONS_LIMIT]
    print(f"   Top {len(institutions)} institutions retrieved")
    return institutions


def fetch_by_year():
    """D. Publications grouped by year."""
    print("4. Fetching publications by year...")
    data = get(f"{BASE}/works", {"filter": VN_FILTER, "group_by": "publication_year"})
    years = []
    for bucket in data.get("group_by", []):
        try:
            year = int(bucket["key"])
        except (ValueError, TypeError):
            continue
        if year >= YEAR_START:
            years.append({
                "year": year,
                "paper_count": bucket["count"],
            })
    years.sort(key=lambda x: x["year"])
    print(f"   Years: {years[0]['year']}–{years[-1]['year']}" if years else "   No year data")
    return years


def fetch_top_cited():
    """G. Top 25 most-cited Vietnam-affiliated papers."""
    print("5. Fetching top cited papers...")
    data = get(f"{BASE}/works", {
        "filter": VN_FILTER,
        "sort": "cited_by_count:desc",
        "select": "id,title,publication_year,cited_by_count,primary_topic,authorships",
        "per-page": str(TOP_CITED_LIMIT),
    })
    papers = []
    for work in data.get("results", []):
        field_name = ""
        if work.get("primary_topic") and work["primary_topic"].get("field"):
            field_name = work["primary_topic"]["field"].get("display_name", "")
        authors = []
        for auth in (work.get("authorships") or [])[:5]:
            author_name = auth.get("author", {}).get("display_name", "Unknown")
            insts = [i.get("display_name", "") for i in auth.get("institutions", [])]
            authors.append({"name": author_name, "institutions": insts})
        papers.append({
            "id": work.get("id", ""),
            "title": work.get("title", ""),
            "year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count", 0),
            "field": field_name,
            "authors": authors,
        })
    print(f"   Top paper: {papers[0]['cited_by_count']:,} citations" if papers else "   No papers")
    return papers


MAX_PAGES_PER_ENTITY = 25  # 25 pages * 200 = 5,000 works sampled per entity


def short_id(full_url):
    """Convert 'https://openalex.org/fields/22' to 'fields/22' for filter use."""
    prefix = "https://openalex.org/"
    return full_url[len(prefix):] if full_url.startswith(prefix) else full_url


def fetch_citations_by_field(fields):
    """F. Sum citations per field using capped cursor pagination with estimation."""
    print("6. Fetching citations by field...")
    for i, field in enumerate(fields):
        field_id = short_id(field["field_id"])
        filt = f"{VN_FILTER},primary_topic.field.id:{field_id}"
        print(f"   [{i+1}/{len(fields)}] {field['field_name']}...")
        citations, _ = cursor_paginate_sum(
            f"{BASE}/works", {"filter": filt}, max_pages=MAX_PAGES_PER_ENTITY
        )
        field["total_citations"] = citations
        field["avg_citations"] = round(citations / field["paper_count"], 2) if field["paper_count"] > 0 else 0
    return fields


def fetch_citations_by_institution(institutions):
    """H. Sum citations per institution using capped pagination."""
    print("7. Fetching citations by institution...")
    for i, inst in enumerate(institutions):
        inst_id = inst["institution_id"]
        filt = f"authorships.institutions.id:{inst_id}"
        print(f"   [{i+1}/{len(institutions)}] {inst['institution_name']}...")
        citations, _ = cursor_paginate_sum(
            f"{BASE}/works", {"filter": filt}, max_pages=MAX_PAGES_PER_ENTITY
        )
        inst["total_citations"] = citations
        inst["avg_citations"] = round(citations / inst["paper_count"], 2) if inst["paper_count"] > 0 else 0
    return institutions


def fetch_citations_by_year(years):
    """I. Sum citations per publication year using capped pagination."""
    print("8. Fetching citations by year...")
    for i, yr in enumerate(years):
        filt = f"{VN_FILTER},publication_year:{yr['year']}"
        print(f"   [{i+1}/{len(years)}] Year {yr['year']}...")
        citations, _ = cursor_paginate_sum(
            f"{BASE}/works", {"filter": filt}, max_pages=MAX_PAGES_PER_ENTITY
        )
        yr["total_citations"] = citations
        yr["avg_citations"] = round(citations / yr["paper_count"], 2) if yr["paper_count"] > 0 else 0
    return years


def fetch_total_citations():
    """E. Total citations across all VN-affiliated works (sampled estimate)."""
    print("9. Fetching total citations (sampled estimation)...")
    citations, works = cursor_paginate_sum(
        f"{BASE}/works", {"filter": VN_FILTER}, max_pages=100
    )
    print(f"   Total citations: {citations:,} (based on {works:,} works)")
    return citations


def main():
    print("=" * 60)
    print("BambooScholar — OpenAlex Data Update")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)

    # Fetch core counts
    total_papers = fetch_total_count()
    fields = fetch_by_field()
    institutions = fetch_by_institution()
    years = fetch_by_year()
    top_cited = fetch_top_cited()

    # Fetch citation data (heavy — uses cursor pagination)
    fields = fetch_citations_by_field(fields)
    institutions = fetch_citations_by_institution(institutions)
    years = fetch_citations_by_year(years)
    total_citations = fetch_total_citations()

    # Current year publications
    current_year = datetime.now(timezone.utc).year
    current_year_papers = next(
        (y["paper_count"] for y in years if y["year"] == current_year), 0
    )

    # Build summary
    avg_citations = round(total_citations / total_papers, 2) if total_papers > 0 else 0
    summary = {
        "total_papers": total_papers,
        "total_citations": total_citations,
        "current_year": current_year,
        "current_year_papers": current_year_papers,
        "avg_citations_per_paper": avg_citations,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "data_source": "OpenAlex",
    }

    # Save all JSON files
    print("\nSaving JSON files...")
    save_json("summary.json", summary)
    save_json("by_field.json", fields)
    save_json("by_institution.json", institutions)
    save_json("by_year.json", years)
    save_json("top_cited.json", top_cited)

    # Save per-institution field breakdowns for top 10
    print("\n10. Fetching per-institution field breakdowns (top 10)...")
    for inst in institutions[:10]:
        inst_id = inst["institution_id"]
        inst_id_short = inst_id.split("/")[-1] if "/" in inst_id else inst_id
        print(f"   {inst['institution_name']}...")
        data = get(f"{BASE}/works", {
            "filter": f"authorships.institutions.id:{inst_id}",
            "group_by": "primary_topic.field.id",
        })
        inst_fields = []
        for bucket in data.get("group_by", []):
            inst_fields.append({
                "field_id": bucket["key"],
                "field_name": bucket["key_display_name"],
                "paper_count": bucket["count"],
            })
        inst_fields.sort(key=lambda x: x["paper_count"], reverse=True)
        save_json(f"institution/{inst_id_short}.json", {
            "institution_id": inst_id,
            "institution_name": inst["institution_name"],
            "fields": inst_fields,
        })

    print("\n" + "=" * 60)
    print("Update complete!")
    print(f"  Papers: {total_papers:,}")
    print(f"  Citations: {total_citations:,}")
    print(f"  Fields: {len(fields)}")
    print(f"  Institutions: {len(institutions)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
