# Contributing to Datakrit

Thank you for helping. Bug reports with a small synthetic reproducer are as valuable as code.
Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md);
questions and early ideas are welcome in
[Discussions](https://github.com/JudikaM/datakrit/discussions).

## Development setup

Python 3.11 or newer. The tested tool versions are pinned in `constraints-dev.txt`.

Windows PowerShell:

```powershell
git clone https://github.com/JudikaM/datakrit.git
cd datakrit
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
python -m mypy
python -m pytest --cov --cov-report=term-missing
python -m build
python -m twine check --strict dist/*
python scripts/smoke_dist.py dist
```

Use the virtual environment's interpreter (`.\.venv\Scripts\python.exe` or
`.venv/bin/python`). `scripts/smoke_dist.py` installs the built wheel into a fresh temporary
environment and runs the documented commands; delete old files in `dist/` first so that it
finds exactly one wheel. It also checks that the wheel holds only the `datakrit` package,
that `python -m datakrit shortcut install --no-desktop --folder DIR` (the command that the
1.2.0 update runs) replaces shortcuts made by 1.x, and that `update --version 1.2.0` is
refused (nothing is downloaded). `--work-dir DIR` puts the temporary environment into DIR.

CI also audits the packages pinned in `constraints-dev.txt` for known vulnerabilities, on
every pull request and weekly. To run the audit yourself, install `pip-audit` in a separate
environment (so that `constraints-dev.txt` can still be regenerated from the development
environment) and run
`pip-audit --requirement constraints-dev.txt --no-deps --disable-pip`. CodeQL analyzes the
Python code and the local interface's JavaScript on pull requests and weekly; its findings
appear in the repository's Security tab.

## Building the Windows app

The Windows app (`Datakrit-X.Y.Z-windows-x64.zip`, see the README) is built from
`packaging/windows/` with PyInstaller. Its build tools are not dependencies of Datakrit:
they are pinned with hashes in `constraints-exe.txt` and installed into a separate virtual
environment. On 64-bit Windows with a 64-bit Python 3.11 or newer (CI uses the newest
supported Python), from the repository root:

```powershell
py -3 -m venv build\venv-exe
.\build\venv-exe\Scripts\python.exe -m pip install --require-hashes -r constraints-exe.txt
.\build\venv-exe\Scripts\python.exe -m pip install --no-deps .
.\build\venv-exe\Scripts\python.exe packaging\windows\build_app.py
.\build\venv-exe\Scripts\python.exe packaging\windows\smoke_app.py dist-exe\Datakrit-X.Y.Z-windows-x64.zip
```

`build\` and `dist-exe\` are ignored by Git.

- `build_app.py` runs PyInstaller with `packaging/windows/datakrit.spec` (a one-folder
  build without a console window that bundles the installed `datakrit` package, its
  interface files, the icon `datakrit.ico`, and version information from `__init__.py`),
  then writes `dist-exe/Datakrit/` with its `licenses` folder, the zip, and its `.sha256`
  file. The license notices come from `LICENSE`, `NOTICE.md`, the `LICENSE.txt` of the
  Python that builds the app (it must be a Windows build from python.org, whose license
  includes the conditions for the Microsoft runtime files), and the installed tomli-w. It refuses to build
  when the installed package is not the version in `src/datakrit/__init__.py`: install it
  again with `pip install --no-deps .` after a change. `dist-exe/` is never committed.
- `smoke_app.py` starts the app (or the unzipped zip, or any `datakrit-ui` program) in smoke
  mode: the environment variable `DATAKRIT_UI_URL_FILE` makes it write its page address to a
  file instead of opening a browser. The script fetches the page and every file of the page
  with the session key, checks that requests without the key are refused, presses Quit, and
  checks that the program exits with code 0. For `Datakrit.exe` and the zip it first checks
  the `licenses` folder. It prints the start-up time.
- The `Windows app` workflow does the same on every pull request and keeps the zip as a
  workflow artifact for 14 days; release builds are described in
  [docs/RELEASE.md](docs/RELEASE.md).
- To update PyInstaller, change its version and the versions of the packages it needs in
  `constraints-exe.txt`, list the SHA-256 of every file PyPI publishes for each version, and
  build and smoke-test the app again. The dependency audit covers this file too.

## Working on the local interface

The interface is `src/datakrit/ui.py` (server) and `src/datakrit/ui_static/` (`index.html`,
`app.css`, `theme.js`, `app.js`, `logo-mark.png`). Its structure is described in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#the-local-page) and its behavior in
[docs/CONFIGURATION.md](docs/CONFIGURATION.md#local-interface).

- **Content security policy.** The page allows only its own files. Do not add inline styles
  (`style="..."`), inline event handlers (`onclick="..."`), inline `<script>` or `<style>`,
  `innerHTML`, or `eval`; build elements with `document.createElement` and set text with
  `textContent`. `test_page_is_self_contained_and_needs_the_key` checks this.
- **No external assets.** No CDN, web fonts, remote images, or requests. Icons are inline SVG
  paths in `currentColor`. An icon from a set that `NOTICE.md` does not cover yet needs its
  copyright and license notice there. A new static file must be added to `STATIC` in
  `ui.py`, to `UI_ASSETS` in `scripts/smoke_dist.py`, to `ASSETS` in
  `packaging/windows/smoke_app.py`, and to the asset test.
- **Accessibility.** Every control needs a name (an icon-only button an `aria-label`), a
  button that shows or hides something needs `aria-controls` and `aria-expanded`, and every
  action must work with the keyboard alone. Keep `prefers-reduced-motion` working.
- **Contrast.** Text needs at least 4.5:1 and icons and focus rings at least 3:1 against
  their background, in both themes (dark and light). Measure new color pairs in the
  browser (for example with the contrast checker of the browser's developer tools) and give
  the numbers in the pull request.
- **Tests.** `python -m pytest tests/integration/test_ui.py` covers the page structure, the
  server, and the API; run the whole suite before a pull request. Changes to the layout or
  behavior also need a walk-through in a real browser in both themes at 1440, 1024, and 390
  pixels wide, recorded in [TEST_CASES.md](TEST_CASES.md#checks-of-the-local-interface-in-a-browser).
- **Screenshots.** The README images in `docs/images/` (`interface-*.png` and
  `interface-preview-*.png`, dark and light) are taken at 1440 x 900 with the example file
  `transactions_fixable.csv` and the profile `examples/profiles/transactions-id.toml`, after
  **Check** and **Preview cleaning**. Retake both themes when the page changes visibly.

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
   (see [docs/RELEASE.md](docs/RELEASE.md)). [docs/STABILITY.md](docs/STABILITY.md) lists
   the whole public surface; update it when you add to that surface.

Review focuses on data integrity first (no silent changes, no guessing, no lost records),
then clarity of messages, then code simplicity.

## Code style

- Runtime code uses the standard library plus `tomli-w`. Discuss new runtime dependencies in an
  issue first.
- Never use floats for numeric data; parse decimal text exactly.
- Core modules must not print or exit; only `cli.py` talks to the terminal.
- User-facing text is English and includes a concrete suggestion.

By contributing you agree that your contributions are licensed under the MIT License.
