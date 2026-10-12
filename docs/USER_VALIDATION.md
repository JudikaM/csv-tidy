# User validation plan

**Status (2026-10-13): no external users have tried CSV Tidy yet.** Everything below is a
plan; field validation is not complete. Benchmarks, synthetic examples, and maintainer testing
are not evidence of usefulness to others.

## Assumptions to validate

1. People who prepare CSV imports regularly meet mixed number conventions, numeric date
   ambiguity, stray whitespace, duplicates, and missing values.
2. They can describe their data in a small TOML profile (possibly by copying an example, or
   with `csv-tidy profile init`), or with the controls of the local interface.
3. English reports with record/line locations and suggestions are understandable, including
   for non-developers.
4. Explicit, opt-in repairs are preferred over automatic "smart" fixes.
5. The `id`, `us`, and `canonical` grammars and numeric date formats cover their data.
6. Performance is adequate for the file sizes they handle.
7. People who work in Excel and do not use a command line can complete a check and a clean
   with the local interface, and understand what was and was not checked.

## Proposed pilot

A small experiment with a few volunteers from the intended groups (developers building
import pipelines, administrators preparing exports, small organizations). This target is
the maintainer's own plan, not a requirement of any program.

Participants use their own **non-sensitive or synthetic** files. Nobody sends data to the
maintainer.

Step-by-step task lists for both groups, with completion criteria and a recording template,
are in [USER_TESTING.md](USER_TESTING.md): one for developers (commands, batch, API) and one
for administrative staff (the local interface). The short list below is the minimum.

### Tasks

1. Install CSV Tidy from the README.
2. Run `csv-tidy check` on a CSV file with an example profile adapted to the file.
3. Explain in your own words what one reported issue means and how you would fix it.
4. Preview fixes with `csv-tidy clean ... --dry-run`.
5. Export with `--apply --output ... --output-schema ...`.
6. Check the exported file with the generated profile.

### Questions

- What kind of CSV files do you work with, and where do they go afterwards?
- Which problems do you hit most often? How do you handle them today?
- Was any message unclear or misleading? Which one?
- Was writing or adapting the profile hard? What did you get wrong first?
- Is anything missing that would stop you from using this regularly?
- Would you use it again? For what?

## Capturing results

For each participant and task, record: completed (yes/partly/no), time taken (rough),
points of confusion (verbatim if possible), and unmet needs. Store notes privately; publish
only aggregated, anonymized findings with consent.

### Feedback template (participants may paste this into an issue)

```markdown
**Role / context:** (e.g. "developer importing supplier price lists"; no company names needed)
**CSV Tidy version:** csv-tidy --version
**Tasks completed:** check / dry run / apply / re-check
**What worked well:**
**What was confusing (exact message if possible):**
**What is missing:**
**Would you use it again? Why / why not:**
**May we quote this anonymously?** yes / no
```

## From feedback to changes

1. Each concrete problem becomes a GitHub issue (with a synthetic reproducer), labeled and
   prioritized as described in [MAINTENANCE.md](MAINTENANCE.md).
2. Fixes reference the issue; the changelog credits the report (anonymously unless agreed).
3. Aggregated findings are added to [IMPACT.md](IMPACT.md) with dates and consent status.

## Invitation draft (not sent)

> Hi! I maintain CSV Tidy, a small open-source command-line tool (MIT, Python, runs offline)
> that checks CSV files for problems like mixed number formats (1.250,50 vs 1,250.50),
> ambiguous dates, duplicates, and missing values, and repairs only what you explicitly
> select. It is new and has not been tested by other people yet. Would you try it on a
> non-sensitive CSV file for about 20 minutes and tell me what was confusing or missing?
> No data needs to be shared with me. Instructions: https://github.com/JudikaM/csv-tidy
> Thank you!
