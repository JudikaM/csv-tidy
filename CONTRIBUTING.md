# Contributing to CSV Tidy

Thank you for helping. Bug reports with a small synthetic reproducer are as valuable as code.
Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md);
questions and early ideas are welcome in
[Discussions](https://github.com/JudikaM/csv-tidy/discussions).

## Development setup

Python 3.11 or newer. The tested tool versions are pinned in `constraints-dev.txt`.

Windows PowerShell:

```powershell
git clone https://github.com/JudikaM/csv-tidy.git
cd csv-tidy
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-dev.txt -e ".[dev]"
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -c constraints-dev.txt -e ".[dev]"
```

## Checks (the same commands run in CI)

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m build
python scripts/smoke_dist.py dist
```

Use the virtual environment's interpreter (`.\.venv\Scripts\python.exe` or
`.venv/bin/python`). `scripts/smoke_dist.py` installs the built wheel into a fresh temporary
environment and runs the documented commands; delete old files in `dist/` first so that it
finds exactly one wheel.

## Adding tests, fixtures, and regressions

- Test observable behavior: issue codes, counts, record/line locations, exit codes, and
  output values. Avoid mocking internal functions.
- Unit tests live in `tests/unit/`, end-to-end CLI tests in `tests/integration/`. Use the
  `write` and `examples` fixtures from `tests/conftest.py` so tests never write into the
  repository.
- Every bug fix gets a regression test that fails without the fix.
- Fixtures must be synthetic. Never commit real customer, employee, or personal data, even
  "anonymized" exports. Use `example.com` addresses and invented identifiers.
- If you add or change an acceptance criterion, update [TEST_CASES.md](TEST_CASES.md).
- Behavior changes must update [docs/CONFIGURATION.md](docs/CONFIGURATION.md), the README,
  and [CHANGELOG.md](CHANGELOG.md) in the same pull request.

## Pull requests

1. Open an issue first for larger changes, so that the design can be agreed on.
2. Keep pull requests focused; one change per pull request.
3. Run the checks above and describe how you verified the change in the PR template.
4. Profile keys, report fields, issue codes, and exit codes are public contracts. Changing
   them needs a changelog entry and, for incompatible changes, a version plan
   (see [docs/RELEASE.md](docs/RELEASE.md)).

Review focuses on data integrity first (no silent changes, no guessing, no lost records),
then clarity of messages, then code simplicity.

## Code style

- Runtime code uses the standard library plus `tomli-w`. Discuss new runtime dependencies in an
  issue first.
- Never use floats for numeric data; parse decimal text exactly.
- Core modules must not print or exit; only `cli.py` talks to the terminal.
- User-facing text is English and includes a concrete suggestion.

By contributing you agree that your contributions are licensed under the MIT License.
