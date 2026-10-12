# User testing guides

Two task lists for trying CSV Tidy: one for developers who use the commands or the Python
API, and one for administrative staff who use the local interface. They are meant for a
first session of 20 to 30 minutes with a facilitator who watches and takes notes.

**Status (2026-10-13): these guides have not been run with any external user yet.** There are
no pilot results. Nothing here is evidence that the tasks are easy or that the tool is useful;
that is what the sessions are meant to find out. The research questions and the plan for
handling feedback are in [USER_VALIDATION.md](USER_VALIDATION.md).

## Rules for every session

- Use **synthetic or non-sensitive files**. The files in `examples/` are enough for every
  task. Participants who bring their own file keep it on their own computer; nobody sends
  data to the maintainer.
- The facilitator does not explain the tool beyond the preparation step. When a participant
  is stuck for more than two minutes, note where, then give the smallest hint that helps.
- Ask participants to think aloud. Write down their words, especially for messages they
  misread.
- Record for each task: completed (yes / with a hint / no), rough time, what was confusing,
  and what the participant expected to happen instead.

## Preparation (facilitator)

1. Install CSV Tidy from a source checkout as described in the [README](../README.md).
2. Confirm that `.\.venv\Scripts\csv-tidy.exe --version` prints a version (on Linux/macOS:
   `.venv/bin/csv-tidy --version`).
3. For the administrative guide, start `.\.venv\Scripts\csv-tidy.exe ui` and leave the
   console window open. If the browser does not open, copy the printed address into it.
4. Make a working copy of `examples/` so the participant cannot damage the originals.

## Guide for developers

Goal: find out whether a developer can go from an unknown CSV file to an automated,
repeatable check without reading the source code.

| # | Task | The task is done when |
|---|------|-----------------------|
| D1 | Check `examples\transactions_unfixable.csv` without a profile (`--delimiter ";"`). Say whether the file is fine. | The participant says, unprompted, that only the structure was checked and values were not. |
| D2 | Create a profile for that file with `csv-tidy profile init` and declare `amount` as a decimal in `id` format, `date` as `DD/MM/YYYY`, and `transaction_id` as required and unique. | A profile file exists and `check --schema` reports the invalid date and the invalid number. |
| D3 | For `examples\transactions_fixable.csv` with `examples\profiles\transactions-id.toml`: check, preview the clean, and explain which problems are repaired and which would remain. | The participant points at `Still to fix` and `FIXED` correctly. |
| D4 | Export the cleaned file and its output profile, then prove that the export is valid. | `check` on the output with the generated profile exits with 0. |
| D5 | Process all `transactions_*.csv` files in `examples\` in one command, write the files that can be written, and produce a JSON summary. State the exit code and what it means. | Two `*.clean.csv` files exist, the blocked ones do not, and the participant explains exit code 1. |
| D6 | Use the JSON report of D5 in a script (any language) to print the names of the blocked files. | The script prints the two blocked files. |
| D7 | From Python, clean one file with `clean_file` and handle the case where export is blocked. | The participant uses `export_ready` or `export_blocked_reason`. |

Questions afterwards:

- Which line of a report did you read first? Was the verdict where you expected it?
- Was it clear what was *not* checked in D1? What made it clear, or what was missing?
- Did any exit code surprise you?
- What would you need before putting `batch` into a scheduled job?
- What did you look for in `--help` and not find?

## Guide for administrative staff

Goal: find out whether someone who works with Excel, and does not use a command line, can
check and clean a file with the local interface, and understands what the tool did and did
not do.

The participant starts at the open page. The facilitator does not touch the mouse or keyboard.

| # | Task | The task is done when |
|---|------|-----------------------|
| A1 | Open `transactions_fixable.csv` from the examples folder. | The preview shows five separate columns (the participant switched the separator to semicolon after the "one wide column" message). |
| A2 | Without changing anything else, select **Check file**. Say whether the data is correct. | The participant says that values were not checked yet, and why. |
| A3 | Tell the tool that `amount` is a number written like `1.250,50`, that `date` is a date written like `DD/MM/YYYY`, and that `transaction_id` must be unique and not empty. Check again. | The check lists two problems, and the participant can say in which row and column they are. |
| A4 | Make the tool repair the two problems, and look at what it will change before saving anything. | "Trim spaces" is ticked for the two columns, and the participant finds the before/after table. |
| A5 | Also have amounts written like `1250.50` and dates like `YYYY-MM-DD` in the cleaned copy. | "Convert format" is ticked for both columns, the two output formats are chosen, and the preview says it is ready to save. |
| A6 | Save the cleaned file, then save the rules so a colleague can reuse them. | A `*.clean.csv` and a `*.profile.toml` are in the download folder. |
| A7 | Open `transactions_unfixable.csv`. Try to save a cleaned copy. Explain why it does not work and what you would do. | The participant reads the blocked message and names the three values to correct in the original file. |
| A8 | Load the rules saved in A6 for a new file (`transactions_valid.csv`) instead of setting them by hand. | The rules appear in step 3 without manual entry and the check passes. |
| A9 | Stop the tool. | **Quit CSV Tidy** was used, or the participant asks how; note which. |

Things to watch without asking:

- Does the participant notice the status strip at the top, and read the "Next:" line?
- Do the words "separator", "encoding", "profile", "record", and "file line" make sense to
  them? Which word do they use instead?
- When a setting is changed after a check, do they understand why the earlier result
  disappeared?
- Do they believe that their original file was not changed? What convinces them?
- Can the whole flow be done with the keyboard only (Tab, Space, Enter, arrow keys)? Ask one
  participant to try.
- On a small laptop screen (about 1366 x 768), is anything cut off or hard to reach?

Questions afterwards:

- In your own words, what did the tool do to your file?
- Was there a moment when you were unsure whether something had been saved or changed?
- Which message was hardest to understand? (Ask for the exact text.)
- How do you do this work today? Would this replace a step, add a step, or neither?
- What would stop you from using this next week?

## Recording template

```markdown
**Guide:** developer / administrative staff
**Date, CSV Tidy version, operating system, browser (if used):**
**Participant context:** (role only; no names or company names)

| Task | Completed (yes / hint / no) | Time | What was confusing (verbatim if possible) |
|------|-----------------------------|------|-------------------------------------------|
| ...  |                             |      |                                           |

**Unprompted comments:**
**Answers to the questions:**
**Bugs seen (with the exact steps):**
**May we quote this anonymously?** yes / no
```

Findings go into GitHub issues with a synthetic reproducer, and aggregated results are added
to [IMPACT.md](IMPACT.md) only with consent, as described in
[USER_VALIDATION.md](USER_VALIDATION.md).
