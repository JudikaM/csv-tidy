## What changes and why

<!-- Link the issue if there is one: Fixes #123 -->

## Behavior and compatibility

- [ ] No change to profile keys, issue codes, report fields, or exit codes
- [ ] Contract change, documented in CHANGELOG.md and docs/CONFIGURATION.md

## Verification

<!-- Paste the commands you ran and their results. -->

- [ ] `python -m ruff check .` and `python -m ruff format --check .`
- [ ] `python -m pytest`
- [ ] `python -m build` and `python scripts/smoke_dist.py dist` (for packaging changes)
- [ ] New or changed behavior has tests; bug fixes include a regression test
- [ ] Test data is synthetic; no real personal or customer data is included
