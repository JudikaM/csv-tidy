# Release process

## Versioning

CSV Tidy uses Semantic Versioning. The package version lives in `src/csv_tidy/__init__.py`.
Being in 0.x does **not** permit silent behavior changes: any change to profile keys or
meaning, report fields, issue codes, exit codes, or the public API must be listed in
[CHANGELOG.md](../CHANGELOG.md). Incompatible changes require a minor version bump in 0.x,
a migration note, and, for profiles or reports, a new `schema_version` with a documented
upgrade path. Existing release tags are never moved or overwritten; a broken release is fixed
by a new patch version.

## Gates (all required)

1. `CHANGELOG.md`: move the Unreleased entries under the new version and date.
2. Update the version in `src/csv_tidy/__init__.py`.
3. Locally, from a clean checkout: `python -m ruff check .`, `python -m ruff format --check .`,
   `python -m pytest`, `python -m build`, `python scripts/smoke_dist.py dist`.
4. Merge the release commit into `main` through a pull request, then wait for the CI workflow
   to pass on **the resulting `main` commit** (Linux and Windows, Python 3.11 and 3.15).
   `main` is protected by a ruleset: changes need a pull request whose four CI jobs passed,
   and force pushes and deleting the branch are refused.
5. Create an annotated tag `vX.Y.Z` pointing to that `main` commit, and a GitHub release from
   the tag.
6. Attach the wheel and sdist built from the tagged commit. The release notes are the
   changelog section for that version and describe only what is implemented.
7. Smoke-test from the tag in a fresh environment, for example:
   `python -m pip install "csv-tidy @ git+https://github.com/JudikaM/csv-tidy@vX.Y.Z"` and
   the README quick start, or `scripts/smoke_dist.py` with the attached wheel.

PyPI publication is not part of this process yet. Before any PyPI release, verify that the
normalized name `csv-tidy` is available, and document the decision.

## Release notes template

```
## CSV Tidy X.Y.Z

Summary of changes for users.

### Added / Changed / Fixed
- ...

### Upgrade notes
- Profile/report compatibility: unchanged | changed (see migration)

### Verification
- CI run: <link to the run for the tagged commit>
- Smoke test: wheel installed in a fresh environment on <OS/Python>
```
