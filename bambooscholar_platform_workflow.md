# BambooScholar Platform — Full Build Workflow (with Citations)

A comprehensive, step-by-step workflow for building and monetizing a Vietnamese academic publications and citations dashboard, powered by OpenAlex and hosted on GitHub Pages with weekly auto-updates.

---

## 1. Platform Definition

**Goal:** A public website and embedded dashboard that tracks the number of scientific publications and citation counts by Vietnamese-affiliated authors, broken down by field and institution, and updated weekly automatically.

**Counting rule:**
- A publication counts if at least one author lists an institution in Vietnam (`authorships.institutions.country_code: VN`)
- A citation count is the aggregate of `cited_by_count` values across all matching publications
- "First-author Vietnamese" is a stricter variant: only count papers where `authorships[0].author_position == "first"` AND at least one institution in that first authorship has `country_code == "VN"`

**Document type:** Start with all OpenAlex `type` values, then optionally restrict to `article` only using the `type` filter once you decide on your methodology.

---

## 2. Data Architecture

### 2.1 OpenAlex API Queries

The weekly updater script makes the following grouped API calls. Each returns a lightweight JSON response with counts — no raw record downloads needed.

#### A. Total publications (Vietnam-affiliated)
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN
```
Read `meta.count` from the response. This is the national total.

#### B. Publications by field
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN&group_by=primary_topic.field.id
```
Returns buckets: `key`, `key_display_name`, `count` per field.

#### C. Publications by institution
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN&group_by=institutions.id
```
Returns buckets: institution name and paper count.

#### D. Publications by year
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN&group_by=publication_year
```
Returns annual publication counts.

#### E. Total citations (sum of `cited_by_count`)
OpenAlex does not provide a direct "sum of citations" in one `group_by` call. Use one of these strategies:
- **Strategy 1 (lightweight):** Retrieve the top N papers sorted by `cited_by_count:desc` with `select=id,cited_by_count,primary_topic`, iterate pages, and sum. Suitable for total + top-cited leaderboard.
- **Strategy 2 (comprehensive):** Query all VN-affiliated works and use **Cursor Pagination** (`&cursor=*`) to iterate through all results efficiently. Sum the `cited_by_count` across all pages. *Do not use standard offset pagination (`page=1,2...`) as OpenAlex limits it to 10,000 results.*

#### F. Citations by field
For each field bucket from Query B, run:
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN,primary_topic.field.id:{field_id}&sort=cited_by_count:desc&select=id,cited_by_count&cursor=*
```
Use Cursor Pagination to fetch all results and sum `cited_by_count` to get total citations per field.

#### G. Most-cited papers leaderboard
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN&sort=cited_by_count:desc&select=id,title,publication_year,cited_by_count,primary_topic,authorships&per-page=25
```
Returns the top 25 most-cited Vietnam-affiliated papers for a leaderboard widget.

#### H. Citations by institution
For each top institution from Query C:
```
GET https://api.openalex.org/works?filter=authorships.institutions.id:{institution_id}&select=id,cited_by_count&per-page=200
```
Paginate and sum for total citations per institution.

#### I. Year-by-year citations
Use `counts_by_year` from individual work records, or query:
```
GET https://api.openalex.org/works?filter=authorships.institutions.country_code:VN,publication_year:{YYYY}&select=id,cited_by_count
```
For each year of interest, sum `cited_by_count` to get total citations received by that year's publications.

### 2.2 Generated JSON Outputs

The updater writes these files into `data/` after each weekly run:

| File | Contents |
|---|---|
| `data/summary.json` | Total publications, total citations, last_updated date |
| `data/by_field.json` | Publications + citations per field |
| `data/by_institution.json` | Publications + citations per institution (top 50) |
| `data/by_year.json` | Annual publications + citations from 2000–present |
| `data/top_cited.json` | Top 25 most-cited papers with metadata |
| `data/by_field_first_author.json` | Publications where first author is Vietnam-affiliated |
| `data/institution/{id}.json` | Field breakdown for individual institutions (generated per institution) |

### 2.3 Python Script Logic (updater pseudocode)

```python
import requests, json, time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://api.openalex.org"
HEADERS = {"User-Agent": "DuongTa/1.0 (tpduong.vie@gmail.com)"}  # identifiable
API_KEY = "Hs3AKBn2jGZm1mUHSwfOPb"

# Configure retry logic with exponential backoff for 429 and 50X errors
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 429, 500, 502, 503, 504 ])
session.mount('https://', HTTPAdapter(max_retries=retries))

def get(url):
    params = {"api_key": API_KEY}
    r = session.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    time.sleep(0.1)  # stay lightweight
    return r.json()

# 1. Total count
meta = get(f"{BASE}/works?filter=authorships.institutions.country_code:VN")
total_papers = meta["meta"]["count"]

# 2. By field
field_data = get(f"{BASE}/works?filter=authorships.institutions.country_code:VN&group_by=primary_topic.field.id")
# field_data["group_by"] is a list of {key, key_display_name, count}

# 3. By institution
inst_data = get(f"{BASE}/works?filter=authorships.institutions.country_code:VN&group_by=institutions.id")

# 4. By year
year_data = get(f"{BASE}/works?filter=authorships.institutions.country_code:VN&group_by=publication_year")

# 5. Top cited papers
top_cited = get(
    f"{BASE}/works?filter=authorships.institutions.country_code:VN"
    "&sort=cited_by_count:desc&select=id,title,publication_year,cited_by_count,primary_topic,authorships&per-page=25"
)

# 6. Total citations (sum from top papers + paginate if needed)
# See section 2.1E for strategy

# ... save all outputs to data/*.json
```

Note: Always check `X-RateLimit-Remaining` response headers and back off on `429` responses. OpenAlex now uses API keys and $1/day free credit per key.

---

## 3. Repository Structure

```
bambooscholar/
├── .github/
│   └── workflows/
│       └── weekly-update.yml       ← GitHub Actions schedule
├── scripts/
│   ├── update_data.py              ← OpenAlex fetcher
│   └── requirements.txt            ← requests, etc.
├── data/                           ← generated JSON (committed by CI)
│   ├── summary.json
│   ├── by_field.json
│   ├── by_institution.json
│   ├── by_year.json
│   ├── top_cited.json
│   └── institution/
├── site/                           ← static HTML/CSS/JS dashboard
│   ├── index.html                  ← home dashboard
│   ├── fields.html
│   ├── institutions.html
│   ├── top-cited.html
│   └── methodology.html
├── docs/
│   └── methodology.md              ← counting rules, caveats
└── README.md
```

---

## 4. Weekly Updater — GitHub Actions YAML

```yaml
# .github/workflows/weekly-update.yml
name: Weekly Data Update

on:
  schedule:
    - cron: '0 8 * * 1'    # Every Monday 08:00 UTC
  workflow_dispatch:         # Manual trigger for hotfixes

permissions:
  contents: write            # allow committing data/ changes
  pages: write
  id-token: write

jobs:
  update-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r scripts/requirements.txt

      - name: Run OpenAlex updater
        env:
          OPENALEX_API_KEY: ${{ secrets.OPENALEX_API_KEY }}
        run: python scripts/update_data.py

      - name: Validate JSON outputs
        run: |
          python -c "
          import json, sys, os
          
          files = ['data/summary.json','data/by_field.json','data/by_institution.json','data/by_year.json']
          for f in files:
              data = json.load(open(f))
              print(f'Valid JSON format: {f}')
              
          # Semantic check to prevent deploying blank data if API failed silently
          summary = json.load(open('data/summary.json'))
          if summary.get('total_papers', 0) == 0:
              print('ERROR: total_papers is 0. Aborting deployment.')
              sys.exit(1)
          "

      - name: Commit updated data
        run: |
          git config user.name "VietPulse Bot"
          git config user.email "bot@vietpulse.io"
          git add data/
          git diff --staged --quiet || git commit -m "chore: weekly data update $(date -u +%Y-%m-%d)"
          # Note: If repository history size becomes a problem long-term due to JSON bloat, 
          # consider pushing this data to an orphan branch (e.g., gh-pages-data) or using GitHub Releases.
          git push

      - name: Setup Pages
        uses: actions/configure-pages@v4

      - name: Upload site artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: './site'

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

**Key notes:**
- Store your OpenAlex API key in GitHub → Settings → Secrets → `OPENALEX_API_KEY`
- The workflow commits refreshed `data/` JSON before deploying, so the static site always serves the latest numbers
- `workflow_dispatch` lets you trigger a manual run any time from the GitHub Actions UI

---

## 5. Dashboard Pages & Metrics

### 5.1 Homepage (index.html)

**KPI row (top of page):**
- Total Vietnam-affiliated publications (all-time)
- Total citations received
- Publications in the current year
- Average citations per paper

**Charts:**
- Yearly trend line: publications count and citations count on dual axis, 2000–present
- Field breakdown bar chart: top 10 fields by paper count
- "Last updated" badge showing the date in `summary.json`

### 5.2 Fields page (fields.html)

- Sortable table: Field name | Paper count | Total citations | Avg citations per paper
- Bar chart: paper count per field
- Bar chart: citation count per field (shows impact, not just volume)
- Toggle between "all works" and "first-author Vietnamese only"

### 5.3 Institutions page (institutions.html)

- Sortable table: Institution | Papers | Total citations | Avg citations per paper | Top field
- Click-through to individual institution page showing field breakdown
- Note: one paper may appear under multiple institutions (methodology caveat displayed on page)

### 5.4 Top Cited page (top-cited.html)

- Ranked list of top 25 most-cited Vietnam-affiliated papers
- Columns: Rank | Title | Year | Field | Citations | Link to OpenAlex record
- Note: First-author filter toggle (show all vs first-author only)

### 5.5 Methodology page (methodology.html)

- Definition: affiliation-based counting, `country_code: VN`
- Document type coverage (all works or articles only)
- Data source: OpenAlex (version, last snapshot date)
- Known limitations: institution-level double counting, citation lag, `is_authors_truncated` edge cases
- Update schedule: every Monday 08:00 UTC

---

## 6. Citation Data: What to Show and How

### 6.1 Per-paper citations
Every OpenAlex Work object includes `cited_by_count` (integer, lifetime citations) and `counts_by_year` (annual breakdown). Both are returned by default in any Works API response at no extra API cost.

### 6.2 Dashboard citation metrics

| Metric | How computed | Where displayed |
|---|---|---|
| Total national citations | Sum of `cited_by_count` across all VN-affiliated works | Homepage KPI |
| Citations by field | Sum per `primary_topic.field.id` group | Fields page |
| Citations by institution | Sum per `authorships.institutions.id` | Institutions page |
| Avg citations/paper | Total citations ÷ total papers | Homepage + all detail pages |
| Citation trend by year | Sum of `cited_by_count` for works published in year Y | Homepage trend chart |
| Top cited leaderboard | Sort by `cited_by_count:desc`, top 25 | Top Cited page |

### 6.3 Citation caveats to display

- `counts_by_year` totals may not exactly match `cited_by_count` due to indexing lag — display note on methodology page
- OpenAlex citation coverage is large but not exhaustive (it does not include all grey literature or some conference-only venues)
- Field Weighted Citation Impact (FWCI) — which normalizes for field and year — requires additional computation and is a good premium feature for a later stage

---

## 7. OpenAlex API Best Practices

| Practice | Why |
|---|---|
| Include `User-Agent` header with contact email | Keeps your traffic identifiable; OpenAlex asks for this |
| Store and use your API key | Required since February 2026; tracked against $1/day free credit |
| Use `group_by` grouped queries when possible | One request returns aggregated counts; avoids downloading raw records |
| Use `select=` to limit fields on raw record requests | Reduces response size significantly |
| Add `time.sleep(0.1)` between requests | Stay well within rate limits |
| Check `X-RateLimit-Remaining` headers | Allows script to self-monitor and back off if needed |
| Never call OpenAlex from the browser | All API calls happen in the weekly CI job; browser reads pre-saved JSON only |
| Validate JSON before committing | Prevents broken data from being deployed to the live site |

---

## 8. Monetization Stages

### Stage 1 — Free public dashboard (launch)
- Host on GitHub Pages (free)
- Public OpenAlex data, open methodology
- Add a donation/sponsorship link (permitted by GitHub Pages terms)
- Grow SEO traffic, academic citations, backlinks
- Build newsletter/mailing list of repeat visitors

### Stage 2 — Paid deliverables (3–6 months post-launch)
- Custom PDF reports: "Vietnam AI Research 2020–2025 by Institution"
- Historical CSV exports (full dataset downloads for researchers)
- One-off commissioned analyses for universities, think tanks, media
- Price: $500–$1,000+ per report depending on complexity (B2B pricing)
- Use Gumroad, Lemon Squeezy, or direct invoice for payment
- *Crucial context:* To sell data successfully, consider making the fetching pipeline/repository Private so the raw JSON/CSV files aren't freely available online to anyone who finds the repository.

### Stage 3 — B2B subscriptions (6–18 months)
- Institution profile pages with full field mix, yearly trends, citation rankings, peer benchmarks
- Private comparison dashboards (e.g., "compare VNU Hanoi vs VNU HCM")
- Email/Slack alerts when rankings change significantly
- Move off GitHub Pages to Vercel/Cloudflare Pages at this stage for authenticated features
- Price: $500–$2,000/year per institution subscriber

### Stage 4 — API and licensing (18+ months)
- Paid API access: authenticated endpoints returning pre-aggregated Vietnam publication data
- White-label data widgets for ed-tech, recruitment, or policy platforms
- Bulk data licensing for research or consulting firms
- Requires custom backend (lightweight Python/Node API + managed database)
- Price: usage-based or annual license

---

## 9. Technology Decisions by Stage

| Stage | Hosting | Auth | Payments | Backend |
|---|---|---|---|---|
| Stage 1 | GitHub Pages | None | Donation link | Lightweight SSG (Astro, Vite, Eleventy) + static JSON |
| Stage 2 | GitHub Pages | None | Gumroad / LemonSqueezy | Lightweight SSG (Astro, Vite, Eleventy) + static JSON |
| Stage 3 | Vercel / Cloudflare Pages | Clerk / Supabase Auth | Stripe | Lightweight FastAPI or Next.js API routes |
| Stage 4 | VPS or managed cloud | API key management | Stripe / usage billing | Full REST API + PostgreSQL or DuckDB |

---

## 10. 12-Week Execution Plan

| Week | Milestone |
|---|---|
| 1 | Finalize methodology (counting rule, document types, field grouping). Register OpenAlex API key. Create GitHub repo. |
| 2 | Build and test `update_data.py` script locally. Validate all 7 JSON outputs. |
| 3 | Set up GitHub Actions weekly workflow. Run first CI deployment to GitHub Pages. |
| 4 | Build homepage (KPI cards + trend chart + field bar chart). Verify mobile. |
| 5 | Build Fields page (sortable table + citation columns). Add first-author toggle. |
| 6 | Build Institutions page. Build Top Cited leaderboard page. |
| 7 | Build Methodology page. Add download buttons (CSV exports from JSON). |
| 8 | QA all pages (desktop + mobile). Fix contrast, chart labels, empty states. |
| 9 | Register domain (.com and .vn). Configure GitHub Pages custom domain. |
| 10 | Soft launch: share with academic networks, Twitter/X, LinkedIn, Vietnamese university groups. |
| 11 | Collect feedback. Fix bugs. Write first custom PDF report as a product sample. |
| 12 | Publish sample report. Set up Gumroad storefront. Begin Stage 2 monetization. |

---

## 11. Known Limitations and Caveats

- **The Diaspora Effect:** The counting rule `country_code: VN` only captures research output generated *within* Vietnam. It does not track globally prominent scholars of Vietnamese descent working at institutions outside Vietnam.
- **Double counting at institution level:** A paper with two Vietnam-affiliated authors at different institutions counts once per institution. National totals use deduplication by work ID; institution totals do not.
- **No double counting in Fields:** We use `primary_topic.field.id` to strictly assign each paper to exactly one field. This prevents double-counting papers across multiple disciplines, ensuring the sum of field counts equals the total.
- **`is_authors_truncated`:** OpenAlex truncates authorship lists to 100 entries for works with many authors. For first-author checks this is safe (position 0 is always included), but middle/last author positions may be affected.
- **Citation lag:** New papers take weeks to months to accumulate citations; `cited_by_count` for very recent publications will be near zero.
- **OpenAlex coverage:** OpenAlex is comprehensive but does not index all grey literature, some conference-only venues, or all predatory journals. Counts will differ from Scopus or Web of Science.
- **`counts_by_year` vs `cited_by_count`:** OpenAlex documents note these may not sum identically due to indexing updates. Display a methodology note on the site.
