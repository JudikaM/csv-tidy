# Impact and evidence

This file records verifiable evidence about CSV Tidy's use and maintenance. Unknown values stay
unknown; they are not estimated or replaced by other metrics.

## Intended problem and benefit

CSV files cross tools and locales. `1.250,50` (Indonesian) and `1,250.50` (US) denote the same
amount; `01/02/2026` is either 1 February or 2 January. Silent misreading during import
causes wrong totals and dates. CSV Tidy aims to make such problems visible with precise
locations and to repair only explicitly selected issues, refusing to export invalid results.

## Usage evidence

Last verified: 2026-10-11.

| Evidence | Value | Source |
|----------|-------|--------|
| External users who tried the tool | none known | no reports received |
| Consented case studies / downstream projects | none | — |
| GitHub stars, forks, clones, traffic | not recorded here yet | repository Insights (maintainer access) |
| PyPI downloads | not applicable (not published on PyPI) | — |
| Issues/PRs from people other than the maintainer | none | GitHub issues |

Stars, downloads, clones, real users, and downstream dependencies are different things and are
listed separately when available.

## Feedback and resulting fixes

None yet. Feedback collected as described in [USER_VALIDATION.md](USER_VALIDATION.md) will be
summarized here with dates, consent status, and links to resulting issues and fixes.

## Releases and maintenance

- Releases: published versions are listed on the
  [GitHub Releases page](https://github.com/JudikaM/csv-tidy/releases); each version's changes
  are in [CHANGELOG.md](../CHANGELOG.md). 0.1.0 is the first version; 0.2.0 adds the profile creator, the local interface, and
  batch processing, none of which has been tried by external users yet.
- Maintainer: JudikaM (repository owner). Responsibilities: triage, reviews, releases, and
  security reports, as described in [MAINTENANCE.md](MAINTENANCE.md).

## Missing evidence

- Any external use or feedback.
- Any downstream project depending on CSV Tidy.
- A maintenance history beyond the initial release.
