# Security policy

## Supported versions

CSV Tidy is in early development. Security fixes are made for the latest released version
only.

## Reporting a vulnerability

Please do not put vulnerability details, exploit files, or real data in a public issue.

GitHub private vulnerability reporting is **not enabled** for this repository yet. Until it is,
open a [public issue](https://github.com/JudikaM/csv-tidy/issues/new) titled
"Security contact request" **without any details**, and the maintainer will arrange a private
way to share them. Once private reporting is enabled, use **Security > Report a vulnerability**
on the repository page instead. This file will be updated when that happens.

This is a volunteer-maintained project. There is no guaranteed response time, but reports are
taken seriously and acknowledged as soon as possible.

## Scope

CSV Tidy runs locally, makes no outgoing network connections, and executes no code from CSV
content or profiles. `csv-tidy ui` opens a listening socket on the loopback address
(`127.0.0.1`) only, for the browser on the same computer; requests need the session key
printed at start-up. Relevant issues include, for example: a way to use the local interface
from another computer, from a web page of another origin, or without the session key; cell
content being interpreted as HTML or script by the page; writing outside the requested output paths,
overwriting input files, crashes or unbounded resource use on crafted input beyond the
documented limits, and data being silently changed. Spreadsheet formula injection in CSV
content is a known property of the CSV format (see the README); CSV Tidy reports values as
they are and does not neutralize formulas.
