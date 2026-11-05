# Maintenance

## Issue triage

1. **Label**: `bug`, `enhancement`, `question`, `documentation`; add `data-integrity` for any
   report of silent value changes, lost records, or wrong validation results.
2. **Reproduce** with the reporter's synthetic file and command. Ask for a minimal synthetic
   reproducer if none is provided; never ask for real personal or customer data.
3. **Prioritize**:
   - P0: data integrity (silent changes, input overwritten, invalid output declared valid).
   - P1: crashes, wrong exit codes, misleading messages.
   - P2: missing conventions or formats requested by real users.
   - P3: convenience and documentation.
4. **Close the loop**: link the fixing PR and release, and thank the reporter.

## Fixing

- Write a regression test that fails first (see [CONTRIBUTING.md](../CONTRIBUTING.md)).
- Keep fixes small; separate refactors from behavior changes.
- Update docs and the changelog in the same pull request.

## Review checklist

- Does any path change a value that the user did not select?
- Are counts, record indexes, and line numbers still correct?
- Are new messages English, specific, and paired with a suggestion?
- Does a new feature reach the data only through `api.py`, so the commands, batch
  processing, and the local interface cannot disagree?
- For the local interface: is file content inserted as text only, does the page still load
  nothing external, and does every request still need the session key?
- Are public contracts (profile keys, issue codes, report fields, exit codes) unchanged, or
  versioned and documented?

## Releases

Follow [RELEASE.md](RELEASE.md). Releases are cut when user-visible changes have accumulated
or a P0/P1 fix is ready; there is no fixed schedule.

## Format and contract changes

New number grammars, date tokens, or profile keys are additive and keep `schema_version = 1`.
Removing or changing the meaning of existing keys requires a new schema version and a
migration note.

## Renaming to Datakrit

**Done (2026-11-05).** 2.0.0 gave the product its current name (decision in
[STABILITY.md](STABILITY.md#the-rename-to-datakrit-in-200)). The checklist, in the order it
was followed so that the 1.2.0 `update` keeps working for installed versions:

- [x] Release 1.2.0 and wait until it is the latest release.
- [x] Rename the repository under **Settings → General → Repository name** to `datakrit`.
  GitHub redirects the old address, also in its API.
- [x] Update the repository description and topics.
- [x] Do the 2.0.0 work: the rename of the code, the documentation, and the release.

Never create a new repository under the old name: it would take the old address and break
that redirect, which installs of 1.2.0 still use to find Datakrit. How each installed
version upgrades is in the [changelog](../CHANGELOG.md#upgrading-to-200).

## Roadmap (driven by feedback)

Candidates, to be prioritized by real user requests rather than built speculatively:

- Streaming processing for files larger than memory.
- Additional number grammars (for example space or apostrophe grouping) and textual month
  names with explicit language selection.
- Date-time values.
- Opt-in delimiter detection with explicit confirmation.
- `.xlsx` input, hosted or multi-user web access, database targets (deferred; not planned
  for 0.x). The local, single-user interface (`datakrit ui`) exists; changes to it should
  come from sessions described in [USER_TESTING.md](USER_TESTING.md).
- A native file dialog for the local interface.
- [x] A self-contained Windows executable: done in 2.1.1 (the Windows app,
  `Datakrit-X.Y.Z-windows-x64.zip`, built by the `Windows app` workflow).
- Code signing for the Windows app, so that SmartScreen does not warn on its first start
  (open: needs a code-signing certificate or a signing service).
- macOS shortcuts.
- Translations of messages/documentation if users need them.
