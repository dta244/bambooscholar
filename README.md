# BambooScholar

A public dashboard tracking Vietnamese scientific publications and citation counts, powered by [OpenAlex](https://openalex.org) and hosted on GitHub Pages with weekly auto-updates.

## Features

- **National KPIs**: Total publications, citations, and averages for Vietnam-affiliated research
- **Field breakdown**: Papers and citations by academic discipline
- **Institution rankings**: Top 50 Vietnamese institutions by output and impact
- **Top cited papers**: Leaderboard of the 25 most-cited Vietnam-affiliated works
- **Weekly updates**: Automated data refresh every Monday via GitHub Actions

## How It Works

1. A Python script (`scripts/update_data.py`) queries the OpenAlex API for Vietnam-affiliated works
2. It generates aggregated JSON files in `data/`
3. GitHub Actions runs this weekly, commits the data, and deploys the static dashboard to GitHub Pages
4. The dashboard (HTML/CSS/JS in `site/`) reads the JSON and renders charts and tables client-side

## Setup

### Prerequisites
- Python 3.12+
- An [OpenAlex API key](https://openalex.org/pricing)

### Local Development

```bash
pip install -r scripts/requirements.txt
OPENALEX_API_KEY=your_key python scripts/update_data.py
# Then serve site/ with any static server
```

### GitHub Pages Deployment

1. Push this repo to GitHub
2. Add your API key as a repository secret: Settings > Secrets > `OPENALEX_API_KEY`
3. Enable GitHub Pages (Settings > Pages > Source: GitHub Actions)
4. Trigger the workflow manually or wait for the Monday schedule

## Counting Methodology

- A publication counts if at least one author lists a Vietnamese institution (`country_code: VN`)
- Citations use OpenAlex's `cited_by_count` (lifetime citations)
- Fields use `primary_topic.field.id` (one field per paper, no double-counting)
- See the [Methodology page](site/methodology.html) for full details and caveats

## Data Source

All data comes from [OpenAlex](https://openalex.org), a free and open catalog of the global research system.

## License

MIT
