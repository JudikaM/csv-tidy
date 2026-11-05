# User testing guides

Two task lists for trying Datakrit: one for developers who use the commands or the Python
API, and one for administrative staff who use the local interface. They are meant for a
first session of 20 to 30 minutes with a facilitator who watches and takes notes.

**Status (2026-11-04): planned after 1.0. These guides have not been run with any external
user, and the interface has not been tried with a screen reader.** Version 1.0.0 was
released without such sessions; its interface was checked only automatically (see
[TEST_CASES.md](../TEST_CASES.md#checks-of-the-local-interface-in-a-browser)). There are no
pilot results. Nothing here is evidence that the tasks are easy or that the tool is useful;
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

1. Install Datakrit from a source checkout as described in the [README](../README.md).
2. Confirm that `.\.venv\Scripts\datakrit.exe --version` prints a version (on Linux/macOS:
   `.venv/bin/datakrit --version`).
3. For the administrative guide, run `.\.venv\Scripts\datakrit.exe shortcut install` once
   for the participant's Windows user, so that a **Datakrit** icon is on the Desktop. Do not
   start Datakrit for them.
4. Make a working copy of `examples/` so the participant cannot damage the originals.

## Guide for developers

Goal: find out whether a developer can go from an unknown CSV file to an automated,
repeatable check without reading the source code.

| # | Task | The task is done when |
|---|------|-----------------------|
| D1 | Check `examples\transactions_unfixable.csv` without a profile (`--delimiter ";"`). Say whether the file is fine. | The participant says, unprompted, that only the structure was checked and values were not. |
| D2 | Create a profile for that file with `datakrit profile init` and declare `amount` as a decimal in `id` format, `date` as `DD/MM/YYYY`, and `transaction_id` as required and unique. | A profile file exists and `check --profile` reports the invalid date and the invalid number. |
| D3 | For `examples\transactions_fixable.csv` with `examples\profiles\transactions-id.toml`: check, preview the clean, and explain which problems are repaired and which would remain. | The participant points at `Still to fix` and `FIXED` correctly. |
| D4 | Export the cleaned file and its output profile, then prove that the export is valid. | `check` on the output with the generated profile exits with 0. |
| D5 | Process all `transactions_*.csv` files in `examples\` in one command, write the files that can be written, and produce a JSON summary. State the exit code and what it means. | Two `*.clean.csv` files exist, the blocked ones do not, and the participant explains exit code 1. |
| D6 | Use the JSON report of D5 in a script (any language) to print the names of the blocked files. | The script prints the two blocked files. |
| D7 | From Python, clean one file with `clean_file` and handle the case where export is blocked. | The participant uses `export_ready` or `export_blocked_reason`. |
| D8 | Find out whether a newer Datakrit exists without installing it. | The participant runs `datakrit update --check`. |

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

The participant starts at the Windows Desktop. The facilitator does not touch the mouse or
keyboard.

| # | Task | The task is done when |
|---|------|-----------------------|
| A0 | Start Datakrit. | The page is open in the browser (from the Datakrit icon); note how long it took to find the icon. |
| A1 | Choose `transactions_fixable.csv` from the examples folder. | The file name is the page title and the preview shows five separate columns: the participant switched **Separator** to **Semicolon** in the file card after the "one wide column" message. |
| A2 | Without changing anything else, select **Check**. Say whether the data is correct. | The participant says that values were not checked yet, and why. |
| A3 | Tell the tool that `amount` is a number written like `1.250,50`, that `date` is a date written like `DD/MM/YYYY` (chosen from the list of date formats), and that `transaction_id` must be unique and not empty. Check again. | The check lists two problems, and the participant can say in which row and column they are and what the "What to do" column suggests. |
| A3b | Show only the problems of the `amount` column. | **Find** in the side bar was used with "amount" (or the participant explains another way). |
| A4 | Make the tool repair the two problems, and look at what it will change before saving anything. | "Trim spaces" is ticked for the two columns, and the participant finds the before/after table. |
| A5 | Also have amounts written like `1250.50` and dates like `YYYY-MM-DD` in the cleaned copy. | "Convert format" is ticked for both columns, the two output formats are chosen, and the preview says it is ready to save. |
| A6 | Save the cleaned file, then save the rules so a colleague can reuse them. | A `*.clean.csv` and a `*.profile.toml` are in the download folder. |
| A7 | Open `transactions_unfixable.csv`. Try to save a cleaned copy. Explain why it does not work and what you would do. | The participant reads the blocked message and names the three values to correct in the original file. |
| A8 | Start again with **New check**, then load the rules saved in A6 for a new file (`transactions_valid.csv`) instead of setting them by hand. | The rules appear without manual entry (from **Load** in the side panel, or in step 3), the **Profile** row names the file, and the check passes. |
| A9 | Switch to **Several files**, choose `transactions_fixable.csv`, `transactions_unfixable.csv`, and `transactions_valid.csv`, load the rules saved in A6, and preview the cleaning of all files. Say which files can be saved and why one cannot. | The participant names the blocked file and its reason (from the table, or from its entry under **In this session**) without opening the CLI. |
| A10 | Save all results as one ZIP and say what is inside. | The participant notices that the blocked file is in the ZIP only as a report. |
| A11 | Close the browser tab without using Quit, then start Datakrit again from the icon. | The page opens again; note whether the participant expected the earlier page to still work. |
| A12 | Stop the tool. | **Quit Datakrit** was used, or the participant asks how; note which. |

Things to watch without asking:

- Does the participant notice the status line above the steps, and read the "Next:" line?
- Do they use the one button in the file card (**Check**, **Preview cleaning**, **Save**), the
  step buttons, or the side bar to move on? Do they find the side panel on the right?
- Do first-time users open **How to use** at the bottom of the side panel, and when? Does it
  help them finish the task (for example, do they follow a step link), or do they ignore it?
- Do they understand that **In this session** is forgotten after Quit?
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

## Results (to fill in)

One row per task and session. No session has been run yet.

| Session | Guide | Task | Completed (yes / hint / no) | Time | Main problem seen | Issue |
|---------|-------|------|-----------------------------|------|-------------------|-------|
| — | — | — | — | — | — | — |

## Screen-reader checklist (NVDA on Windows)

Planned after 1.0; not run yet. Use NVDA with Firefox or Chrome on Windows, the page at its
default size, and the files in `examples/`. Record each item as pass, fail (with what NVDA
said), or not checked.

| # | Check | Expected |
|---|-------|----------|
| S1 | Press `D` (landmarks) repeatedly | "Side bar navigation", "main", "complementary" (and "banner" in a narrow window) |
| S2 | Press `H` / `1` | One heading level 1: the page title (the file name once a file is chosen) |
| S3 | Tab from the top of the page | First stop: "Skip to the main column"; Enter moves to the main column |
| S4 | Tab through the side bar | Every button is read with its name; the fold button says "Side bar, expanded" or "collapsed"; Find says "collapsed"/"expanded" |
| S5 | Open Find, type a word | The count ("2 of 5 rows in this step match") is announced; Escape empties, then closes |
| S6 | Choose a file in the file card | The status line announces what happened and the next step |
| S7 | Separator and mode chips | Read as radio buttons in a group named "Separator" or "Files"; arrow keys change them |
| S8 | Check with the primary button | The result is announced in the status line; the problems table is reachable and read with its column headers |
| S9 | Column rules in step 3 | Each control names its column, for example "What column amount contains" |
| S10 | **In this session** | Each file is read with its rows and state, for example "transactions_fixable.csv 4 rows · problems found" |
| S11 | Side panel | Each row is read as a term and its value; actions are read as "Load a profile", "Edit the column rules", and so on |
| S12 | New check and Quit | The dialog is announced with its title and text; focus starts on the safe button; Escape closes it |
| S13 | Narrow window (or zoom 400 %) | The side bar opens over the page from the top bar; focus stays inside it; Escape returns to the button |

## Recording template

```markdown
**Guide:** developer / administrative staff
**Date, Datakrit version, operating system, browser (if used):**
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
