# Release process

## Versioning

Datakrit uses Semantic Versioning. The package version lives in `src/datakrit/__init__.py`.
Being in 0.x does **not** permit silent behavior changes: any change to profile keys or
meaning, report fields, issue codes, exit codes, or the public API must be listed in
[CHANGELOG.md](../CHANGELOG.md). Incompatible changes require a minor version bump in 0.x,
a migration note, and, for profiles or reports, a new `schema_version` with a documented
upgrade path. Existing release tags are never moved or overwritten; a broken release is fixed
by a new patch version.

From 1.0.0 the covered surface and the rules for major, minor, and patch releases are those
in [STABILITY.md](STABILITY.md), which also lists that surface in full. Before a release,
compare its changelog entries with that list: a change to a listed item in a minor or patch
release must be a compatible addition.

## Distribution channels

Every release is published in three ways, all from the same tag:

| Channel | Files | Made by |
|---------|-------|---------|
| GitHub release | `datakrit-X.Y.Z-py3-none-any.whl`, `datakrit-X.Y.Z.tar.gz` | built locally from the tagged commit and attached by hand (below) |
| GitHub release | `Datakrit-X.Y.Z-windows-x64.zip` and `.zip.sha256` | the `windows-app.yml` workflow, run for the tag |
| PyPI (`pip install datakrit`) | the wheel and sdist of the GitHub release, unchanged | the `publish-pypi.yml` workflow, when the release is published |

`publish-pypi.yml` downloads the wheel and sdist from the published GitHub release, checks
each file against the SHA-256 that GitHub publishes for it, runs `twine check --strict`,
checks that the version equals the tag, and uploads both files through PyPI Trusted
Publishing (the PyPI project trusts this workflow in the GitHub environment `pypi`; there is
no token). It never builds anything and never uploads the zip. A version can be uploaded to
PyPI only once: PyPI refuses the same file name again, also after a deletion.

## Gates before the tag (all required)

1. `CHANGELOG.md`: move the Unreleased entries under the new version and date.
2. Update the version in `src/datakrit/__init__.py`, and the version shown in the README
   (sample output and the file names in "Installation"; `tests/unit/test_release_metadata.py`
   checks the sample output).
3. Locally, from a clean checkout: `python -m ruff check .`, `python -m ruff format --check .`,
   `python -m mypy`, `python -m pytest`, `node --check` on the interface scripts,
   `python -m build`, `python -m twine check --strict dist/*`,
   `python scripts/smoke_dist.py dist`, and the Windows app: `packaging/windows/build_app.py`
   and `packaging/windows/smoke_app.py` on the zip (see CONTRIBUTING.md, "Building the
   Windows app").
4. Merge the release commit into `main` through a pull request, then wait for the CI workflow
   to pass on **the resulting `main` commit** (Linux and Windows, Python 3.11 and 3.15), and
   for the `Windows app` workflow on that commit. `main` is protected by a ruleset: changes
   need a pull request whose four CI jobs passed, and force pushes and deleting the branch
   are refused.

## Releasing, in this order

1. **Tag.** Create an annotated tag `vX.Y.Z` pointing to that `main` commit.
2. **Draft release.** Build the wheel and sdist from the tagged commit (a clean checkout or
   `git archive` of the tag), smoke-test them (`scripts/smoke_dist.py`), and create a
   **draft** GitHub release of the tag with both files attached. A draft is not visible to
   users and starts no workflow.
3. **Windows app.** Run `gh workflow run windows-app.yml -f tag=vX.Y.Z`. The workflow checks
   out the tag, checks that its version is X.Y.Z, builds the app, smoke-tests the zip, and
   attaches `Datakrit-X.Y.Z-windows-x64.zip` and its `.sha256` file to the draft release.
   It refuses a tag without a draft release.
4. **Check the zip.** Download it from the draft, compare its SHA-256 with the `.sha256` file
   and with the digest GitHub shows for the asset, and smoke-test it on Windows:
   `python packaging/windows/smoke_app.py Datakrit-X.Y.Z-windows-x64.zip --sha256 <hash>`.
5. **Release notes.** Use the changelog section for the version (describe only what is
   implemented), and list the SHA-256 of all three files: the wheel, the sdist, and the zip.
   Check the text with the publication helper's `check-text`.
6. **Publish** the release as the latest release.
7. **PyPI.** Publishing starts `publish-pypi.yml`. The `pypi` environment may wait for the
   maintainer's approval under **Actions**; approve it there.
8. **Check PyPI.** In a fresh virtual environment, `python -m pip install datakrit==X.Y.Z`
   (wait a minute if pip does not see the version yet), then `datakrit --version` and
   `datakrit update --check`.
9. **Compare.** Download the wheel that pip installs
   (`python -m pip download datakrit==X.Y.Z --no-deps -d DIR`) and check that its SHA-256
   equals the release asset's.

### When a step fails

- **Before step 6** (gates, tag, draft, zip, notes): do not publish. Fix the cause, and leave
  the draft unpublished or delete it. A tag that points to the wrong commit is never moved:
  the fix is a new patch version. A tag that has no published release yet can stay unused.
- **The Windows app workflow fails:** do not publish. If the cause is outside the repository
  (for example a runner problem), run the workflow again for the same tag; it never
  overwrites an asset, so delete a partly uploaded zip from the draft first. If the code or
  the packaging is wrong, fix it in a pull request and release a new patch version: a zip is
  only ever built from its own tag.
- **`publish-pypi.yml` fails before the upload** (a download, hash, metadata, or version
  check, or an unapproved deployment): nothing reached PyPI. Fix the cause outside the
  release files (for example the Trusted Publisher settings on PyPI or the environment) and
  run `gh workflow run publish-pypi.yml -f tag=vX.Y.Z`. If the release files themselves are
  wrong, release a new patch version.
- **The upload fails part-way, or PyPI shows a broken version:** a file name can never be
  uploaded twice, so a retry fails for a file that already reached PyPI. Yank the incomplete
  or broken version on PyPI and release a new patch version.
- **The installed wheel differs from the release asset (step 9):** stop, yank the version on
  PyPI, report it as a security issue (SECURITY.md), and release a new patch version.

## Release notes template

```
## Datakrit X.Y.Z

Summary of changes for users.

### Added / Changed / Fixed
- ...

### Upgrade notes
- Profile/report compatibility: unchanged | changed (see migration)

### Files (SHA-256)
- datakrit-X.Y.Z-py3-none-any.whl: <hash>
- datakrit-X.Y.Z.tar.gz: <hash>
- Datakrit-X.Y.Z-windows-x64.zip: <hash>

### Verification
- CI run: <link to the run for the tagged commit>
- Windows app: <link to the windows-app run for the tag>
- Smoke test: wheel installed in a fresh environment on <OS/Python>; the zip on Windows
```
