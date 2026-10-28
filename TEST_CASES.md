# Test cases and acceptance criteria

Each acceptance criterion maps to automated tests in `tests/` (run with `python -m pytest`)
or to the distribution smoke test `scripts/smoke_dist.py`. Tests check observable values,
counts, statuses, exit codes, and file contents, not internal calls.

## Acceptance criteria → tests

| ID | Requirement | Tests |
|----|-------------|-------|
| AC-01 | Comma/semicolon, UTF-8 and UTF-8 BOM, explicit encoding, Unicode, CRLF/LF | `unit/test_reader.py`: `test_delimiters_and_line_endings`, `test_utf8_bom_is_detected_and_not_part_of_header`, `test_explicit_encoding` |
| AC-02 | Quoted delimiters, escaped quotes, multiline values, line ranges | `unit/test_reader.py`: `test_quoting_multiline_and_line_ranges`, `test_crlf_inside_quoted_field_is_preserved`; `unit/test_output.py`: `test_render_csv_quotes_and_line_endings` |
| AC-03 | Empty file, header-only file, blank lines | `unit/test_reader.py`: `test_empty_header_only_and_blank_lines`; `unit/test_validation.py`: `test_empty_file_is_an_error_and_header_only_is_a_warning`, `test_blank_lines_are_warnings_with_line_numbers` |
| AC-04 | Empty/duplicate/whitespace headers, missing columns, wrong field counts | `unit/test_validation.py`: `test_header_problems`, `test_missing_profile_column`, `test_possible_wrong_delimiter_hint`, `test_inconsistent_columns`; `unit/test_reader.py`: `test_wrong_field_counts_are_kept_not_dropped` |
| AC-05 | Malformed CSV, strict decoding, field-size limit → fatal, incomplete scan | `unit/test_reader.py`: `test_malformed_quotes_are_fatal_with_partial_scan`, `test_unterminated_quote_is_fatal`, `test_strict_decoding_reports_line_and_does_not_replace`, `test_field_size_limit`, `test_missing_input_and_directory`; `integration/test_cli.py`: `test_incomplete_scan_is_reported_with_exit_2` |
| AC-06 | Required emptiness, whitespace-only, zero, optional empties | `unit/test_validation.py`: `test_required_whitespace_and_zero`, `test_optional_empty_values_are_not_errors` |
| AC-07 | Duplicate rows, single/composite keys, empty keys, keep-first removal | `unit/test_validation.py`: `test_duplicate_rows_warn_and_keys_error`, `test_empty_key_values_never_form_an_identity`, `test_duplicate_row_warnings_can_be_ignored`; `unit/test_normalization.py`: `test_deduplicate_keys_keeps_first_and_marks_source_issue_removed` |
| AC-08 | Leading-zero identifiers and phone numbers stay text | `unit/test_validation.py`: `test_identifiers_keep_leading_zeros`; `unit/test_reader.py`: `test_fields_are_text_and_never_converted`; `integration/test_examples.py`: `test_customers_us_profile_preserves_identifiers` |
| AC-09 | `id`/`us`/`canonical` grammars and normalization | `unit/test_formats.py`: `test_parse_and_normalize_to_canonical`, `test_format_with_grouping`; `unit/test_normalization.py`: `test_normalize_converts_valid_values_and_leaves_invalid_ones`, `test_cli_style_overrides_change_output_format` |
| AC-10 | Grouping, mixed syntax, signs, scale, NaN/Infinity, exponent, currency | `unit/test_formats.py`: `test_invalid_numbers_are_rejected`, `test_invalid_number_explanations`, `test_scale_and_precision_are_preserved_exactly` |
| AC-11 | Invalid dates, leap years, explicit formats, no guessing, invalid directives, compact formats without separators (fixed-width tokens only) | `unit/test_formats.py`: `test_dates_follow_the_configured_format`, `test_invalid_dates_are_rejected`, `test_date_formatting_and_padding`, `test_invalid_date_directives_are_rejected`, `test_compact_dates_without_separators`, `test_invalid_compact_dates_are_rejected`, `test_compact_date_formatting`, `test_ambiguous_or_mixed_compact_formats_are_explained`; `unit/test_normalization.py`: `test_normalize_writes_compact_dates`, `test_normalize_reads_compact_dates`; `unit/test_validation.py`: `test_invalid_number_and_date_messages` |
| AC-12 | Only selected columns are trimmed; others unchanged | `unit/test_normalization.py`: `test_nothing_changes_without_selected_transformations`, `test_trim_only_selected_columns_and_keep_internal_whitespace`, `test_whitespace_is_not_silently_fixed_by_normalize`, `test_records_with_wrong_field_count_are_never_transformed_or_removed` |
| AC-13 | Duplicates introduced by trimming/normalization | `unit/test_normalization.py`: `test_transformations_can_introduce_duplicate_keys`, `test_normalization_can_make_rows_identical`; `integration/test_examples.py`: `test_trim_introduced_duplicates_block_until_deduplicated` |
| AC-14 | `--dry-run`/`--apply` exclusivity; dry run writes no CSV/profile | `integration/test_cli.py`: `test_dry_run_and_apply_are_exclusive`, `test_apply_requires_output_and_output_requires_apply`, `test_dry_run_may_save_a_report_but_no_csv_or_profile` |
| AC-15 | CLI > profile > default; list options replace or clear | `unit/test_schema.py`: `test_defaults_without_profile`, `test_profile_values_and_output_follow_resolved_source`, `test_cli_overrides_win_and_output_follows_the_override`, `test_unspecified_overrides_do_not_replace_profile_values`, `test_list_overrides_replace_rather_than_merge`; `integration/test_cli.py`: `test_cli_options_override_profile`, `test_list_options_replace_or_disable_profile_lists` |
| AC-16 | Unknown keys, schema versions, invalid directives/options, missing references | `unit/test_schema.py`: `test_invalid_profiles_are_rejected`, `test_invalid_overrides_are_rejected`, `test_load_profile_errors`; `integration/test_cli.py`: `test_configuration_errors_exit_2_without_traceback` |
| AC-17 | Input/output identity incl. relative, symlink and hardlink aliases | `unit/test_output.py`: `test_output_cannot_be_the_input`, `test_hardlink_alias_of_input_is_rejected`, `test_symlink_alias_of_input_is_rejected` (skipped where the OS user cannot create symlinks) |
| AC-18 | CSV/report/profile path collisions; input profile protected | `unit/test_output.py`: `test_artifact_collisions_are_rejected`; `integration/test_cli.py`: `test_report_collisions_and_input_protection` |
| AC-19 | Existing output refused unless `--overwrite` | `unit/test_output.py`: `test_existing_output_requires_overwrite`; `integration/test_cli.py`: `test_existing_outputs_and_overwrite` |
| AC-20 | Write failure: temp cleanup, existing file kept, partial outcomes reported | `unit/test_output.py`: `test_failed_replace_keeps_existing_file_and_removes_temp`, `test_profile_write_failure_after_csv_is_reported`, `test_unencodable_output_fails_before_writing`, `test_export_writes_csv_and_profile_and_refuses_blocked_results` |
| AC-21 | JSON validity, totals, severities, scan status, truncation, exit codes, determinism | `integration/test_cli.py`: `test_json_report_contract_and_truncation`, `test_incomplete_scan_is_reported_with_exit_2`, `test_warnings_alone_exit_0`; `unit/test_validation.py`: `test_issue_order_is_deterministic` |
| AC-22 | Output profile reflects resolved CLI overrides | `unit/test_schema.py`: `test_output_profile_uses_resolved_overrides_and_round_trips`, `test_output_profile_keeps_source_format_for_columns_not_normalized`, `test_unusual_column_names_round_trip`; `integration/test_examples.py`: `test_generated_profile_reflects_cli_overrides` |
| AC-23 | Exported CSV passes `check` with the generated profile | `integration/test_examples.py`: `test_transactions_fixable_full_chain`, `test_generated_profile_reflects_cli_overrides`, `test_trim_introduced_duplicates_block_until_deduplicated` |
| AC-24 | Second `clean` with the output profile changes nothing | `integration/test_examples.py`: `test_transactions_fixable_full_chain`, `test_generated_profile_reflects_cli_overrides` |
| AC-25 | CLI/API consistency, `--help`, `--version`, `python -m csv_tidy`, API example | `integration/test_cli.py`: `test_version_and_help`, `test_python_dash_m_runs_the_cli`, `test_cli_and_api_agree`, `test_api_example_runs` |
| AC-26 | Built wheel installs and works in a fresh environment | `scripts/smoke_dist.py` (run locally and in CI after `python -m build`) |
| AC-27 | Source files are never modified | `integration/test_examples.py`: `test_transactions_fixable_full_chain`, `test_unfixable_transactions_block_export`; `scripts/smoke_dist.py` |
| AC-28 | Reports state coverage: structure-only runs are labelled, checked and unchecked columns are listed, JSON has `coverage` | `integration/test_reports.py`: `test_check_without_column_rules_says_only_structure_was_checked`, `test_check_without_column_rules_reports_coverage_in_json`, `test_check_with_a_profile_lists_checked_and_unchecked_columns`, `test_passing_check_with_rules_states_what_passed` |
| AC-29 | Text reports: verdict first, unresolved before repaired, `FIXED`/`REMOVED` separated, next steps; JSON history unchanged | `integration/test_reports.py`: `test_clean_preview_separates_repaired_problems_from_remaining_ones`, `test_blocked_clean_lists_unresolved_problems_first_and_once`, `test_clean_json_keeps_the_issue_history_and_adds_coverage`, `test_incomplete_check_puts_the_stop_location_in_the_verdict`, `test_incomplete_clean_shows_what_was_found_before_the_stop`, `test_duplicates_removed_by_deduplication_are_listed_as_removed` |
| AC-30 | `profile init`: all-text template, no inference, explicit reading settings, non-interactive options never read stdin | `integration/test_profile_init.py`: `test_template_declares_every_column_as_text_and_guesses_nothing`, `test_values_that_look_like_numbers_or_dates_stay_text`, `test_options_build_a_complete_profile_without_prompting`, `test_special_column_names_round_trip` |
| AC-31 | `profile init`: existing destination and input protected, invalid configuration and unusable headers refused, guided mode with re-prompt and cancellation | `integration/test_profile_init.py`: `test_existing_destination_and_inputs_are_protected`, `test_invalid_configuration_writes_nothing`, `test_unusable_headers_are_refused_with_the_reason`, `test_guided_answers_produce_the_same_profile`, `test_guided_mode_reprompts_after_an_invalid_answer`, `test_guided_mode_can_be_cancelled_without_writing` |
| AC-32 | Local interface: same results as the library and CLI, downloads equal the CLI export, blocked/incomplete results cannot be saved, stale results refused | `integration/test_ui.py`: `test_preview_shows_rows_and_never_guesses_the_delimiter`, `test_check_and_clean_match_the_library_results`, `test_downloads_equal_the_cli_export`, `test_blocked_and_incomplete_results_cannot_be_downloaded_as_csv`, `test_results_go_stale_when_the_file_or_settings_change`, `test_invalid_settings_and_profiles_are_explained`, `test_rules_saved_from_the_page_work_with_the_cli` |
| AC-33 | Local interface: loopback only, session key and origin checks, no external resources, content returned as data, private copies removed on quit | `integration/test_ui.py`: `test_page_is_self_contained_and_needs_the_key`, `test_server_listens_on_loopback_only`, `test_requests_without_the_key_or_from_other_origins_are_refused`, `test_uploads_are_private_copies_with_safe_names_and_a_size_limit`, `test_html_in_data_is_returned_as_plain_json_text`, `test_quit_stops_the_server_and_removes_the_temporary_copies` |
| AC-34 | Batch: documented selection, per-file results and totals, aggregate exit code, preview by default | `integration/test_batch.py`: `test_directory_selection_is_documented_sorted_and_not_recursive`, `test_explicit_files_are_taken_as_given_in_order`, `test_empty_and_repeated_selections_are_refused`, `test_batch_check_reports_each_file_and_totals`, `test_aggregate_exit_code_prefers_operational_failures`, `test_batch_clean_is_a_preview_by_default`, `test_batch_report_file_and_text_summary` |
| AC-36 | Interface, several files: one status per file equal to `csv-tidy batch`, per-file details, ZIP with only exportable files plus reports and summary, per-file download gate, stale results, duplicate names refused | `integration/test_ui.py`: `test_batch_gives_each_file_its_own_status_like_the_cli`, `test_batch_file_details_equal_the_single_file_result`, `test_batch_zip_holds_only_exportable_files_and_matches_the_cli`, `test_batch_single_downloads_respect_the_export_gate`, `test_batch_check_mode_and_rules_missing_columns`, `test_batch_refuses_duplicate_names_and_goes_stale`, `test_batch_request_validation`; `integration/test_batch.py`: `test_labels_name_files_in_outcomes_and_reports`; `scripts/smoke_dist.py` (batch and ZIP from the installed wheel) |
| AC-37 | Interface: `max_field_chars` control and display limits (problems, changed values, preview rows) honored, validated, and used by saved reports | `integration/test_ui.py`: `test_report_and_preview_limits_are_honored_and_validated`, `test_default_limits_are_unchanged`, `test_max_field_chars_applies_to_preview_check_and_saved_profiles` |
| AC-38 | Start without a command line: `csv-tidy-ui` (no console), Desktop/Start Menu shortcuts on Windows and Linux, other programs' shortcuts never touched, server stops after inactivity | `integration/test_shortcuts.py`: all tests (Windows `.lnk` created and read back on Windows); `integration/test_ui.py`: `test_idle_server_stops_by_itself_and_contact_keeps_it_running`, `test_requests_without_the_key_do_not_keep_the_server_alive`, `test_run_ui_with_idle_minutes_returns_and_cleans_up`, `test_gui_entry_point_opens_the_browser_without_a_console`, `test_quiet_mode_survives_a_missing_console`, `test_ui_command_accepts_idle_minutes`; `scripts/smoke_dist.py` (program present, shortcuts from the installed wheel) |
| AC-39 | `csv-tidy update`: explicit, verified (SHA-256 from the release), up to date / check-only without pip, failures explained, no network in other commands | `integration/test_update.py`: all tests |
| AC-40 | Issues carry `remedy` (JSON only); the interface explains it with its own controls | `integration/test_remedy.py`: all tests |
| AC-41 | Interface look: self-contained page (own `app.css`, `theme.js`, `app.js`; no inline styles, handlers, or scripts), one server per port | `integration/test_ui.py`: `test_page_is_self_contained_and_needs_the_key`, `test_a_second_server_cannot_share_the_port_of_a_running_one`; `scripts/smoke_dist.py` (`theme.js` in both archives) |
| AC-35 | Batch: deterministic output names, collisions and unsafe paths stop before writing, a failing file does not affect others, single-file commands unchanged | `integration/test_batch.py`: `test_apply_writes_separate_deterministic_outputs_and_skips_blocked_files`, `test_output_name_collisions_stop_the_batch_before_writing`, `test_existing_outputs_and_inputs_are_protected`, `test_one_failed_write_does_not_undo_the_other_files`, `test_overrides_apply_to_every_file`, `test_library_entry_point_matches_the_command`, `test_single_file_commands_are_unchanged_and_help_lists_batch` |

## Regression tests

`tests/integration/test_regressions.py` covers defects found by the audit of commit
`e1e4a63` (R1-R7) and the follow-up audit of `4e5b12a` (RA, RB, RD).

| ID | Defect | Related criteria | Tests |
|----|--------|------------------|-------|
| R1 | A value that fails its source format but looks valid in the output format was marked resolved | AC-09, AC-11, AC-12 | `test_r1_*` (numbers, dates, trim-then-parse, unchanged valid values, removed records) |
| R2 | Export after a working-directory change could overwrite the input CSV/profile | AC-17, AC-27 | `test_r2_export_after_cwd_change_cannot_overwrite_inputs` |
| R3 | Normalized values longer than `max_field_chars` produced an unreadable export | AC-22, AC-23, AC-24 | `test_r3_expanded_output_beyond_field_limit_blocks_export`, `test_r3_chain_stays_valid_when_the_limit_allows_expansion` |
| R4 | A destination created during the write was replaced without `--overwrite` | AC-19, AC-20 | `test_r4_destination_created_during_finalization_is_not_clobbered` |
| R5 | Binary/text-to-text codecs were accepted and crashed | AC-16 | `test_r5_non_text_codecs_are_configuration_errors`, `test_r5_text_encodings_still_work` |
| R6 | Directly constructed `Profile`/`ColumnSpec` objects skipped validation | AC-16, AC-25 | `test_r6_direct_profile_objects_are_validated`, `test_r6_valid_direct_profile_is_supported`, `test_r6_override_lists_must_be_sequences` |
| R7 | A failed `--report` write was not reflected in the printed report | AC-21 | `test_r7_*` |
| RA | List-valued `Profile`/`Overrides` settings broke output-profile generation (follow-up audit of `4e5b12a`) | AC-22, AC-24, AC-25 | `test_ra_*` |
| RB | The `undefined` codec escaped as a raw `UnicodeError` (follow-up audit) | AC-16 | `test_rb_undefined_codec_is_a_configuration_error` |
| RD | Without hard-link support, no-clobber writes fell back to a non-atomic copy (follow-up audit) | AC-19, AC-20 | `test_rd_*` (the hard-link strategy is exercised on every platform) |
| RE | `profile_to_toml` rejected valid list-valued `Profile` collections (follow-up review of `8389d1d`) | AC-22, AC-25 | `test_re_*` |
| RF | A decoding error in a file with CR line breaks was reported on line 1 | AC-05 | `integration/test_reliability.py`: `test_rf_*` (LF, CRLF, CR, lines inside quoted fields, UTF-16) |
| RG | After a decoding error `physical_lines` stayed 0 and readable records were not counted | AC-05, AC-21 | `test_rg_*` (every newline, a file larger than one read buffer, earlier malformed quoting, open quoted field) |
| RH | Overlapping reads shared the process-wide field limit, so a 50-character field passed a limit of 10 | AC-05 | `test_rh_overlapping_reads_each_keep_their_own_field_limit` (both orders), `test_rh_field_limit_boundary_is_unchanged`, `test_rh_global_field_limit_is_restored_after_failures` |
| RI | `export_clean` on an incomplete result said "0 output error(s) remain" | AC-20 | `test_ri_*` |
| — | Parsing contract: a quote inside an unquoted field is kept literally | AC-05 | `test_quote_inside_unquoted_field_follows_python_csv_and_is_kept_literally` |

## Fixture expectations

All fixtures in `examples/` are synthetic. Source file hashes are compared before and after
the commands below.

| Fixture | Profile | `check` | `clean` result |
|---------|---------|---------|----------------|
| `transactions_valid.csv` | `transactions-id.toml` | 0 issues, exit 0 | export ready, exit 0 |
| `transactions_fixable.csv` | `transactions-id.toml` | 2 errors: `invalid_number` (record 2, `amount` `' 980,00 '`), `invalid_date` (record 3, `date` `'28/02/2026 '`); exit 1 | 9 fields changed in 4 records, both issues `resolved`, 0 output issues, exit 0. Output: `1250.50`, `980.00`, `12000`, `-75.25`; dates `2026-02-01`, `2026-02-15`, `2026-02-28`, `2024-02-29`; `customer_id` `00789` trimmed; `note` unchanged |
| output of the row above | generated `transactions.output.toml` | 0 issues, exit 0 | 0 changes, exit 0 |
| `transactions_unfixable.csv` | `transactions-id.toml` | 3 errors: `invalid_date` (record 1, `31/02/2026`), `missing_required` (record 2, `customer_id`), `invalid_number` (record 3, `abc`); exit 1 | 3 `unresolved`, export blocked, no file written, exit 1 |
| `transactions_canonical.csv` | `transactions-canonical.toml` | 0 issues, exit 0 | — |
| `customers_valid.csv` | `customers-us.toml` | 0 issues, exit 0 | — |
| `customers_fixable.csv` | `customers-us.toml` | 2 errors: `invalid_number` (record 1, `credit_limit` `' 1,250.50'`), `invalid_date` (record 2, `signup_date` `' 02/15/2026'`); exit 1 | both `resolved`, export ready, exit 0; record 1 becomes `00123`, `Ada Lovelace`, `081234567890`, `1250.50`, `2026-02-01`; `+62 812 3456 7890` unchanged |
| `customers_trim_duplicates.csv` | `customers-us.toml` | 0 issues, exit 0 (keys differ before trimming) | `duplicate_key` record 2 `introduced`, exit 1; with `--deduplicate keys`: record 2 removed, exit 0, output re-checks cleanly |

## Checks of the local interface in a browser

`tests/integration/test_ui.py` covers the server over HTTP. The page itself was driven in
headless Chrome through the DevTools protocol on 2026-10-13 (Windows 11, Chrome, 1366 x 768
and 1024 x 600), with these observed results:

| Flow | Observed |
|------|----------|
| Empty state | Status "No file chosen yet", every action disabled, steps 2 and 3 explain what will appear |
| Wrong separator | Warning "The file loaded as one wide column"; switching to semicolon reads 4 rows, 5 columns; nothing is guessed |
| Check without rules | Warning "Structure is fine, but no values were checked" |
| Rules set with the controls | Changing a rule clears earlier results; the check finds 2 problems with record, file line, and suggestion |
| Preview without repairs | Saving blocked, reason shown, CSV button disabled, report still available |
| Preview with repairs | "Ready to save: 4 rows, 9 values changed, 0 rows removed"; edge spaces visible; 9 changed cells highlighted |
| Saving | Five downloads; the CSV equals the CLI export; the example file is unchanged |
| Loading a profile | Controls filled from the profile; same result as setting them by hand |
| Unfixable file | Saving blocked with 3 problems |
| Invalid date format, invalid profile file | Explained in the status strip, nothing lost |
| Undecodable file | "This file could not be read to the end" with the file line; choosing the right encoding reads it |
| HTML in cell values | Shown as text; no element is created and no script runs |
| Cancel | "Cancelled. Nothing was changed or saved." |
| Loading state | Progress bar, Cancel button, other actions disabled |
| Keyboard | Skip link first, then controls in order; a 3 px focus outline on each |
| 1024 x 600 | No horizontal page scrolling; the status strip stays at the top while scrolling |
| Labels | Every input, select, and button has an accessible name |
| Network and console | No request to another host, no content-security-policy violation, no script error |
| Quit | Server stops and removes its temporary folder |

For 0.3.0 the same tooling walked through the new features on 2026-10-14 (1366 x 768 and
1024 x 600), and the walk-through above was repeated unchanged (37 checks passed):

| Flow | Observed |
|------|----------|
| Several-files mode | Multiple file input; batch save buttons replace the one-file buttons; four files listed; a picker selects the previewed file |
| Rules for all files | A loaded profile applies to every file |
| Check all files | Problems found, Problems found, No problems, Not fully read; the unreadable file shows `decode_error`; status "3 of 4 files need attention" |
| Preview cleaning of all files | Ready, Blocked, Ready, Not fully read; Save CSV only on ready rows; status names the ready files |
| Details | The blocked file's problems open below the table |
| Downloads | ZIP, one cleaned CSV, and the text summary saved; the ZIP holds cleaned files only for ready files |
| Staleness | Changing a rule clears the batch result and disables the ZIP button |
| Removing a file | The list and the preview update |
| Detail limit 1 | One problem listed, "Showing 1 of 3 problems"; an invalid limit is explained |
| `max_field_chars` 10 | Reading stops with "exceeds the limit of 10 characters"; 0 is refused with an explanation; raising it reads the file; the saved profile contains it |
| Preview rows 1 | One preview row |
| 1024 x 600, labels, network | No horizontal page scrolling; every control has an accessible name; no external request, no CSP violation, no script error |

For 0.4.0 (2026-10-14) the 0.3.0 walk-through (26 checks) and the one-file walk-through (37
checks, adjusted to choose date formats from the list) were repeated and passed, and 13 new
checks passed: date lists filled with example labels, **Other…** hidden until chosen and then
used for a column, the per-column list showing the file's format, a check with list-chosen
formats finding the two whitespace problems, suggestions naming "Repair: trim spaces" and no
command-line option on the page, an invalid date pointing to the format, a profile with an
unlisted format loading into **Other…**, and a stopped server reported as "CSV Tidy is not
running any more" with a pointer to the icon. No external request or script error.

After the redesign (unreleased), 19 further checks passed in headless Chrome: Cosmos dark by
default, theme switch with a notice and remembered after reload, the current step marked in the
step navigation (1, 3, 6 as work progresses), a dropped file read like a chosen one, the
selected option card highlighted, keyboard focus on the hidden file input outlining the drop
area, Quit asking in a dialog (Stay keeps the server, Quit stops it), no horizontal scrolling at
1024 and 390 pixels, every control named, and the lowest text contrast 5.19:1 (dark) and 4.97:1
(light), with white on the primary-button gradient at 6.29:1 and above. The 0.4.0, 0.3.0, and
one-file walk-throughs (13, 26, 37 checks) passed again with the new markup.

`csv-tidy update --check` was run once against the real GitHub API (release 0.3.0): the wheel
and its digest were found and matched the published SHA-256. pip was shown to refuse a wheel
URL whose `#sha256=` fragment does not match and to accept the right one.

These were automated walk-throughs by the maintainer's tooling, not tests with users or with
assistive technology; see [docs/USER_TESTING.md](docs/USER_TESTING.md).

## Manual checks before a release

See [docs/RELEASE.md](docs/RELEASE.md): CI green on the exact commit (Linux and Windows,
Python 3.11 and 3.15), `python -m build`, `python scripts/smoke_dist.py dist`, and the
README commands run from the tagged source.
