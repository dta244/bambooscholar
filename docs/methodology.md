# BambooScholar Methodology

## Counting Rule

A publication is counted as Vietnamese-affiliated if **at least one author** lists an institution in Vietnam (`authorships.institutions.country_code: VN`) in the OpenAlex database.

**Citation count** is the aggregate of `cited_by_count` values across all matching publications.

## Document Types

All OpenAlex `type` values are included: articles, reviews, conference papers, book chapters, preprints, etc.

## Field Classification

Each work is assigned to exactly one field via OpenAlex's `primary_topic.field.id`. This ensures no double-counting across disciplines — the sum of all field counts equals the national total.

## Institution Counting

A paper co-authored by researchers at two different Vietnamese institutions counts once per institution in institution-level totals. National totals are deduplicated by work ID.

## Data Source

- **OpenAlex** (https://openalex.org) — a free, open catalog indexing 250M+ works
- Updated weekly every Monday at 08:00 UTC via GitHub Actions

## Known Limitations

1. **Diaspora effect**: Only research produced within Vietnam is captured. Vietnamese-descent scholars at international institutions without a VN affiliation are not counted.
2. **Institution double-counting**: One paper can appear under multiple institutions.
3. **Author truncation**: OpenAlex truncates authorship lists at 100 entries. First-author checks are safe.
4. **Citation lag**: New papers take weeks/months to accumulate citations.
5. **Coverage**: OpenAlex does not index all grey literature or some conference-only venues.
6. **counts_by_year vs cited_by_count**: May not sum identically due to indexing updates.
