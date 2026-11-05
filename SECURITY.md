# Security policy

## Supported versions

| Version | Security fixes |
|---------|----------------|
| 1.x | Yes: fixes go into the latest 1.x release (a patch release such as 1.0.1, or the next minor release) |
| 0.x | No: upgrade to 1.x (see "Migrating from 0.x" in the README) |

Fixes are made for the latest 1.x release only; upgrading within 1.x keeps profiles,
options, and JSON reports compatible ([docs/STABILITY.md](docs/STABILITY.md)), so there are
no separate fixes for older 1.x releases. `csv-tidy update` installs the latest release.

## Reporting a vulnerability

Please do not put vulnerability details, exploit files, or real data in a public issue.

Report it privately through GitHub:
[**Report a vulnerability**](https://github.com/JudikaM/csv-tidy/security/advisories/new)
(also under **Security > Report a vulnerability** on the repository page). Only you and the
maintainer can see the report, and a fix can be prepared before it becomes public.

This is a volunteer-maintained project. There is no guaranteed response time, but reports are
taken seriously and acknowledged as soon as possible. A confirmed vulnerability is fixed in a
new release, and a GitHub security advisory describes it once the fix is available.

## Automated checks on the repository

Private vulnerability reporting (above), Dependabot alerts, and malware alerts are enabled
for the repository. CI also audits the pinned development packages with `pip-audit`, and
CodeQL analyzes the Python code and the interface's JavaScript; see
[CONTRIBUTING.md](CONTRIBUTING.md#checks-the-same-commands-run-in-ci).

## Scope

CSV Tidy runs locally and executes no code from CSV content or profiles. It makes no outgoing
network connections, except `csv-tidy update` when a user runs it: that command reads the
release information from the GitHub API (`JudikaM/datakrit`, then `JudikaM/csv-tidy`) and
has pip install the release wheel, checked against the SHA-256 that GitHub publishes for it.
For a Datakrit release it then runs Datakrit's own `shortcut install` (only if CSV Tidy made
shortcuts) and pip's uninstall of CSV Tidy. `csv-tidy ui` opens a listening socket on the loopback address
(`127.0.0.1`) only, for the browser on the same computer; requests need the session key
printed at start-up. Relevant issues include, for example: a way to use the local interface
from another computer, from a web page of another origin, or without the session key; cell
content being interpreted as HTML or script by the page; `csv-tidy update` installing a
file other than the verified release wheel; shortcuts changing files they did not create; writing outside the requested output paths,
overwriting input files, crashes or unbounded resource use on crafted input beyond the
documented limits, and data being silently changed. Spreadsheet formula injection in CSV
content is a known property of the CSV format (see the README); CSV Tidy reports values as
they are and neutralizes formulas only in the text columns selected for it. A formula-like
value that the selected neutralization leaves unchanged is a relevant issue.
