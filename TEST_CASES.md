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
| AC-25 | CLI/API consistency, `--help`, `--version`, `python -m datakrit`, API example | `integration/test_cli.py`: `test_version_and_help`, `test_python_dash_m_runs_the_cli`, `test_cli_and_api_agree`, `test_api_example_runs` |
| AC-26 | Built wheel installs and works in a fresh environment | `scripts/smoke_dist.py` (run locally and in CI after `python -m build`) |
| AC-27 | Source files are never modified | `integration/test_examples.py`: `test_transactions_fixable_full_chain`, `test_unfixable_transactions_block_export`; `scripts/smoke_dist.py` |
| AC-28 | Reports state coverage: structure-only runs are labelled, checked and unchecked columns are listed, JSON has `coverage` | `integration/test_reports.py`: `test_check_without_column_rules_says_only_structure_was_checked`, `test_check_without_column_rules_reports_coverage_in_json`, `test_check_with_a_profile_lists_checked_and_unchecked_columns`, `test_passing_check_with_rules_states_what_passed` |
| AC-29 | Text reports: verdict first, unresolved before repaired, `FIXED`/`REMOVED` separated, next steps; JSON history unchanged | `integration/test_reports.py`: `test_clean_preview_separates_repaired_problems_from_remaining_ones`, `test_blocked_clean_lists_unresolved_problems_first_and_once`, `test_clean_json_keeps_the_issue_history_and_adds_coverage`, `test_incomplete_check_puts_the_stop_location_in_the_verdict`, `test_incomplete_clean_shows_what_was_found_before_the_stop`, `test_duplicates_removed_by_deduplication_are_listed_as_removed` |
| AC-30 | `profile init`: all-text template, no inference, explicit reading settings, non-interactive options never read stdin | `integration/test_profile_init.py`: `test_template_declares_every_column_as_text_and_guesses_nothing`, `test_values_that_look_like_numbers_or_dates_stay_text`, `test_options_build_a_complete_profile_without_prompting`, `test_special_column_names_round_trip` |
| AC-31 | `profile init`: existing destination and input protected, invalid configuration and unusable headers refused, guided mode with re-prompt and cancellation | `integration/test_profile_init.py`: `test_existing_destination_and_inputs_are_protected`, `test_invalid_configuration_writes_nothing`, `test_unusable_headers_are_refused_with_the_reason`, `test_guided_answers_produce_the_same_profile`, `test_guided_mode_reprompts_after_an_invalid_answer`, `test_guided_mode_can_be_cancelled_without_writing` |
| AC-32 | Local interface: same results as the library and CLI, downloads equal the CLI export, blocked/incomplete results cannot be saved, stale results refused | `integration/test_ui.py`: `test_preview_shows_rows_and_never_guesses_the_delimiter`, `test_check_and_clean_match_the_library_results`, `test_downloads_equal_the_cli_export`, `test_blocked_and_incomplete_results_cannot_be_downloaded_as_csv`, `test_results_go_stale_when_the_file_or_settings_change`, `test_invalid_settings_and_profiles_are_explained`, `test_rules_saved_from_the_page_work_with_the_cli` |
| AC-33 | Local interface: loopback only, session key and origin checks, no external resources, content returned as data, private copies removed on quit | `integration/test_ui.py`: `test_page_is_self_contained_and_needs_the_key`, `test_server_listens_on_loopback_only`, `test_requests_without_the_key_or_from_other_origins_are_refused`, `test_uploads_are_private_copies_with_safe_names_and_a_size_limit`, `test_html_in_data_is_returned_as_plain_json_text`, `test_quit_stops_the_server_and_removes_the_temporary_copies` |
| AC-34 | Batch: documented selection, per-file results and totals, aggregate exit code, preview by default | `integration/test_batch.py`: `test_directory_selection_is_documented_sorted_and_not_recursive`, `test_explicit_files_are_taken_as_given_in_order`, `test_empty_and_repeated_selections_are_refused`, `test_batch_check_reports_each_file_and_totals`, `test_aggregate_exit_code_prefers_operational_failures`, `test_batch_clean_is_a_preview_by_default`, `test_batch_report_file_and_text_summary` |
| AC-36 | Interface, several files: one status per file equal to `datakrit batch`, per-file details, ZIP with only exportable files plus reports and summary, per-file download gate, stale results, duplicate names refused | `integration/test_ui.py`: `test_batch_gives_each_file_its_own_status_like_the_cli`, `test_batch_file_details_equal_the_single_file_result`, `test_batch_zip_holds_only_exportable_files_and_matches_the_cli`, `test_batch_single_downloads_respect_the_export_gate`, `test_batch_check_mode_and_rules_missing_columns`, `test_batch_refuses_duplicate_names_and_goes_stale`, `test_batch_request_validation`; `integration/test_batch.py`: `test_labels_name_files_in_outcomes_and_reports`; `scripts/smoke_dist.py` (batch and ZIP from the installed wheel) |
| AC-37 | Interface: `max_field_chars` control and display limits (problems, changed values, preview rows) honored, validated, and used by saved reports | `integration/test_ui.py`: `test_report_and_preview_limits_are_honored_and_validated`, `test_default_limits_are_unchanged`, `test_max_field_chars_applies_to_preview_check_and_saved_profiles` |
| AC-38 | Start without a command line: `datakrit-ui` (no console), Desktop/Start Menu shortcuts on Windows and Linux, other programs' shortcuts never touched, server stops after inactivity | `integration/test_shortcuts.py`: all tests (Windows `.lnk` created and read back on Windows); `integration/test_ui.py`: `test_idle_server_stops_by_itself_and_contact_keeps_it_running`, `test_requests_without_the_key_do_not_keep_the_server_alive`, `test_run_ui_with_idle_minutes_returns_and_cleans_up`, `test_gui_entry_point_opens_the_browser_without_a_console`, `test_quiet_mode_survives_a_missing_console`, `test_ui_command_accepts_idle_minutes`; `scripts/smoke_dist.py` (program present, shortcuts from the installed wheel) |
| AC-39 | `datakrit update`: explicit, verified (SHA-256 from the release), up to date / check-only without pip, failures explained, no network in other commands | `integration/test_update.py`: `test_find_release_reads_the_wheel_and_its_published_hash`, `test_unusable_releases_are_refused`, `test_a_specific_version_is_looked_up_by_its_tag`, `test_update_installs_a_newer_release_with_hash_checking`, `test_up_to_date_and_check_only_never_run_pip`, `test_older_releases_are_installed_only_when_asked_for`, `test_network_and_pip_failures_are_explained`, `test_pause_waits_for_enter_so_a_shortcut_window_stays_readable`, `test_only_the_update_command_uses_the_network` |
| AC-40 | Issues carry `remedy` (JSON only); the interface explains it with its own controls | `integration/test_remedy.py`: all tests |
| AC-41 | Interface look: self-contained page (own `app.css`, `theme.js`, `app.js`; no inline styles, handlers, or scripts), one server per port; the page icon and both side-bar logos use `logo-mark.png` (64 x 64 PNG, Datakrit's icon); `logo.png` was removed in 2.0.0 and is not served | `integration/test_ui.py`: `test_page_is_self_contained_and_needs_the_key`, `test_a_second_server_cannot_share_the_port_of_a_running_one`, `test_the_old_logo_with_text_is_gone`, `test_logo_mark_is_served_as_a_png_without_the_key`; `scripts/smoke_dist.py` (`theme.js` and `logo-mark.png` in both archives) |
| AC-42 | Tab-separated files: tab delimiter in profiles (`"\t"`), options (`tab`, a tab, or `\t`), output and output profiles, the single-column hint, next-step commands, `profile init`, and the interface | `integration/test_tab_delimiter.py`: all tests; `integration/test_ui.py`: `test_preview_reads_tab_separated_files` |
| AC-43 | `profile init`: per-column number and date formats as options, validated before writing (unknown column, wrong column type, invalid format, repeated column, missing `=`), column names containing `=` | `integration/test_profile_init.py`: `test_per_column_formats_are_written_and_used`, `test_column_names_may_contain_an_equals_sign`, `test_per_column_format_mistakes_are_refused_before_writing` |
| AC-44 | Opt-in formula neutralization in selected text columns: OWASP triggers get a leading `'`, other values and numbers are unchanged, trimming first, text columns only, missing columns reported, output profile keeps it and a second clean is a no-op, unused selection not written, reports, CLI options, batch, interface | `integration/test_formula_neutralization.py`: all tests; `integration/test_ui.py`: `test_interface_profiles_can_neutralize_formulas` |
| AC-45 | `docs/STABILITY.md` lists the whole covered surface: every command and long option, profile key and value, issue code (the same set as the code), `remedy` value, field of the `check`, `clean`, and `batch` JSON reports, and name in `datakrit.__all__` | `unit/test_stability_inventory.py`: all tests |
| AC-46 | Interface shell: a side bar (`nav`), one main column (`main`) with the only `h1`, and a side panel (`aside`); a skip link as the first stop; side-bar toggles with `aria-controls` and `aria-expanded`; named icon-only buttons; theme switch and Quit in the side bar; the folded state read and written only inside try/catch; a modal overlay below 720 px (Escape, focus kept inside); the step marker follows the last clicked step and moves on with the work | `integration/test_ui.py`: `test_page_shell_has_side_bar_main_column_and_side_panel`, `test_side_bar_state_is_remembered_only_where_storage_works`; browser checks below |
| AC-47 | Input card and step area: file, separator (radio group), encoding, mode (radio group), and the primary button in one card; the size limit from `--max-file-mb` described for the file input; breadcrumb with a file menu (`aria-controls`, `aria-expanded`, Escape, arrow keys); one step shown at a time, the mark moving to the step of the newest result and never back on its own; Check, then Preview cleaning, then Save; a press during a running request waits instead of being lost | `integration/test_ui.py`: `test_input_card_holds_the_file_controls_and_one_primary_button`, `test_step_area_shows_one_step_and_the_primary_button_waits_its_turn`; browser checks below |
| AC-48 | Side-bar sections: **New check** (asks first when anything is loaded; removes the server copies), **Find** (a disclosure with `aria-controls`/`aria-expanded` and a search field that filters the table rows of the step area, also tables drawn later), and **In this session** (each loaded file with rows and a status in an icon and in words; a note that nothing is kept after Quit) | `integration/test_ui.py`: `test_side_bar_has_new_check_find_and_the_session_list`, `test_new_check_removes_the_loaded_files_from_the_session`; browser checks below |
| AC-49 | Side-panel rows Profile, Columns, Unique keys, Output, and Theme, each with its value and a named action (Load/Save, Edit, Add, Edit, Switch) whose name starts with its visible word | `integration/test_ui.py`: `test_side_panel_rows_show_the_current_settings_with_an_action_each`; browser checks below |
| AC-50 | Accessibility of the page: every ARIA and label reference resolves, every disclosure states `aria-expanded`, the landmarks `header`/`nav`/`main`/`aside`, icon-only buttons named, both dialogs labelled with the safe button focused first, a visible focus ring, reduced motion stopping every animation and transition | `integration/test_ui.py`: `test_page_structure_supports_keyboard_and_screen_reader_use`; browser checks below |
| AC-51 | Contract of 1.0.0: `--profile`, `--output-profile`, `--output-profiles`, `export_clean(output_profile=...)` and `run_batch(output_profiles=...)` (their 0.x aliases were removed in 2.0.0, see AC-58), the identifiers introduced with report `schema_version` 2 (`dry_run`, `output_csv`/`output_profile`, a top-level `artifacts` list in clean reports, `output_field_too_large`), `CleanResult.ok`/`source_errors`/`source_warnings`/`output_warnings`, and the new exports | `integration/test_contract_1_0.py`: all tests; `integration/test_regressions.py`: `test_r3_expanded_output_beyond_field_limit_blocks_export`; `unit/test_stability_inventory.py` |
| AC-35 | Batch: deterministic output names, collisions and unsafe paths stop before writing, a failing file does not affect others, single-file commands unchanged | `integration/test_batch.py`: `test_apply_writes_separate_deterministic_outputs_and_skips_blocked_files`, `test_output_name_collisions_stop_the_batch_before_writing`, `test_existing_outputs_and_inputs_are_protected`, `test_one_failed_write_does_not_undo_the_other_files`, `test_overrides_apply_to_every_file`, `test_library_entry_point_matches_the_command`, `test_single_file_commands_are_unchanged_and_help_lists_batch` |
| AC-52 | **How to use** in the side panel: a native `<details>` after the rows and before the "Local only" footer, closed by default; opens and closes with Enter or Space; the open state is remembered under `datakrit-howto` (read and written inside try/catch, so blocked storage only means it starts closed); six step names (data-step 1–6, in order) that show their step like the step navigation; the tip about profiles; the chevron turns when open, without animation under reduced motion; the panel grows downward without changing its width or the main column at 1440, 1024, and 390 pixels. The unused background layer (`.backdrop`, `--nebula-1/2/3`, `--stars`) is gone | `integration/test_ui.py`: `test_side_panel_has_a_closed_how_to_use_guide`, `test_unused_background_layer_is_gone`; browser checks below |
| AC-53 | Focus rings follow the keyboard: a mouse click on the file area, the **Encoding** list, or a list of step 3 draws no ring and the file card keeps its border; Tab to the file field, a separator, or a list shows the ring; the ring around the chosen separator and file mode stays | `integration/test_ui.py`: `test_focus_rings_follow_the_keyboard_not_mouse_clicks`; browser checks below |
| AC-54 | Every single-choice list (10 in the page, the type, number, and date lists of each column rule) draws the chevron of **How to use** instead of the browser's arrow, 12 to 14 pixels from the right edge with room for the text; it turns 180 degrees while the list is open, at once under reduced motion; the multi-select list of combined keys keeps its box | `integration/test_ui.py`: `test_lists_use_the_how_to_use_chevron_which_turns_while_open`; browser checks below |
| AC-55 | Thin scroll bars in both themes: the page, the side bar, the side panel, and tables scroll with a 6-pixel rounded thumb without a track (in the side panel clear of its round corners), at least 3:1 against the surface behind it; other browsers get `scrollbar-width: thin` | `integration/test_ui.py`: `test_scroll_bars_are_thin_in_both_themes`; browser checks below |
| AC-56 | `datakrit update` trusts only `JudikaM/datakrit`: the release lookup, an answer only from `https://api.github.com/` (also after a redirect), the wheel `datakrit-X.Y.Z-py3-none-any.whl` only from `https://github.com/JudikaM/datakrit/releases/download/` with a well-formed `sha256:` digest, the User-Agent `datakrit/<version>`; `update --version` before 2.0.0 refused without going online (exit code 2, hint to install by hand from the Releases page) | `integration/test_update.py`: all tests; `scripts/smoke_dist.py` (`update --version 1.2.0` refused by the installed wheel) |
| AC-57 | Shortcut migration from 1.x: `shortcut install` and `shortcut remove` also remove the shortcuts that 1.x made (they start the 1.x interface program or run the 1.x module; on Linux also the 1.x marker), on the Desktop (also with `--no-desktop`) and in the Start Menu or applications menu, or in `--folder`; files with those names that belong to other programs are kept and not reported; the command that the 1.2.0 update runs (`python -m datakrit shortcut install --no-desktop`) replaces them | `integration/test_shortcuts.py`: the tests under "migration" (real `.lnk` files on Windows, desktop entries on Linux paths, the PowerShell request for the default places); `scripts/smoke_dist.py` (`check_migration` with the installed wheel) |
| AC-58 | Contract of 2.0.0: report `tool.name` `datakrit` and `schema_version` 3, nothing else changed (every example profile with every example file gives the same `check`, `clean`, and `batch` results, cleaned CSV, and output profile as 1.2.0); profiles and output profiles keep `schema_version = 1`; the removed options are usage errors that name the new option and the removed keywords raise `TypeError`; `DatakritError` is the base class; program names, `--version`, and the error prefix `datakrit: error:` | `integration/test_contract_2_0.py`: all tests (fingerprints of 1.2.0 in `integration/results_1_2_0.json`, made with the published 1.2.0 wheel); `scripts/smoke_dist.py` (the wheel holds only the `datakrit` package and the interface files) |
| AC-59 | Interface storage migration: `theme.js` (before the first paint) and `app.js` move a choice stored under a 1.x key to `datakrit-theme`, `datakrit-nav`, or `datakrit-howto` when the new key is missing and remove the old key; a choice under the new key wins; blocked storage moves nothing and breaks nothing | `integration/test_ui.py`: `test_old_stored_choices_move_to_the_new_keys`, `test_a_choice_under_the_new_key_wins_over_the_old_one`, `test_blocked_storage_moves_nothing_and_breaks_nothing` (run in Node.js, skipped without it), `test_stored_choices_are_moved_before_they_are_read` |
| AC-60 | Windows app sources: the launcher calls `datakrit.ui.gui_main` (the entry point of `datakrit-ui`); the PyInstaller spec makes a one-folder build without a console window that collects `ui_static` and every module of the package, with the icon and the version information (product name Datakrit, file description "Datakrit local interface", version from `__init__.py`); the zip holds the folder `Datakrit/`, with `Datakrit/licenses/` holding `LICENSE`, `NOTICE.md`, `Python-LICENSE.txt` (the bundled Python's LICENSE.txt: PSF License, its bundled libraries, and the Microsoft Distributable Code conditions), `tomli-w-LICENSE.txt`, and `Microsoft-runtime-NOTICE.txt` (every bundled Microsoft runtime DLL by path, with those conditions quoted), and nothing else; the build refuses a Python license without the Microsoft section, and the smoke test fails when a notice is missing, lacks its license, or a Microsoft DLL is not named; the smoke test fetches exactly the files in `ui.STATIC`; the build refuses an installed package of another version | `unit/test_windows_app.py`: all tests (`test_the_app_carries_the_notices_of_what_it_bundles`, `test_the_build_refuses_a_python_license_without_the_microsoft_conditions`); the `Windows app` workflow (build and `packaging/windows/smoke_app.py` on every pull request, on `main`, and for a release tag) |
| AC-61 | Smoke mode: with `DATAKRIT_UI_URL_FILE` set, `gui_main` opens no browser and writes the page address with its key to that file (never partly written) before serving; the page and its files are served with the key, a request without the key is refused (403), Quit stops the server, and the program exits with code 0; an empty variable means a normal start | `integration/test_ui.py`: `test_smoke_mode_writes_the_address_instead_of_opening_the_browser`, `test_smoke_mode_serves_the_page_until_quit`; `packaging/windows/smoke_app.py` against the built app (and against `datakrit-ui`) |
| AC-62 | Frozen mode (`sys.frozen`, the Windows app): `update` and `update --check` report the release and `Datakrit-X.Y.Z-windows-x64.zip` with the release page and never run pip (also for `--version`); up to date is reported as such; GitHub unreachable is exit code 2; `shortcut install` is refused (exit code 2, a hint to pin `Datakrit.exe` to Start) and writes nothing; a start-up problem is written to `datakrit-ui-error.txt`, also when the smoke-mode address file cannot be written, and the server and its temporary folder are closed | `integration/test_update.py`: `test_a_pip_install_is_not_frozen`, `test_the_windows_app_reports_the_zip_and_never_runs_pip`, `test_the_windows_app_up_to_date_and_chosen_versions`; `integration/test_shortcuts.py`: `test_the_windows_app_offers_no_shortcuts`; `integration/test_ui.py`: `test_the_windows_app_writes_the_start_up_error_file` |
| AC-63 | Publishing checks: every link and image in the README (the PyPI project page) is an absolute address, and those into the repository name existing files and headings; `twine check --strict` passes in CI; the build tools of the app are pinned with hashes in `constraints-exe.txt` and are no dependency of Datakrit; `publish-pypi.yml` uploads only the wheel and sdist of a published, non-prerelease GitHub release, after checking each file against GitHub's SHA-256, `twine check --strict`, and the version against the tag, through Trusted Publishing in the `pypi` environment with `id-token: write` and `contents: read` only; `windows-app.yml` attaches the zip only to a draft release of the requested tag, with `contents: write` in that job only, and checks GitHub's digest after the upload | `unit/test_release_metadata.py`: `test_readme_links_and_images_work_on_the_pypi_page`; `unit/test_windows_app.py`: `test_build_tools_are_pinned_with_hashes_and_are_never_dependencies`; CI (`twine check`); the workflows themselves at each release (docs/RELEASE.md, steps 3 to 9) |

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
| RJ | A refused request to the local interface could reset the connection before the answer arrived (issue #23) | AC-33 | `integration/test_ui.py`: `test_refused_requests_with_a_body_still_get_their_answer` |
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
unlisted format loading into **Other…**, and a stopped server reported as "Datakrit is not
running any more" with a pointer to the icon. No external request or script error.

After the redesign (unreleased), 19 further checks passed in headless Chrome: Cosmos dark by
default, theme switch with a notice and remembered after reload, the current step marked in the
step navigation (1, 3, 6 as work progresses), a dropped file read like a chosen one, the
selected option card highlighted, keyboard focus on the hidden file input outlining the drop
area, Quit asking in a dialog (Stay keeps the server, Quit stops it), no horizontal scrolling at
1024 and 390 pixels, every control named, and the lowest text contrast 5.19:1 (dark) and 4.97:1
(light), with white on the primary-button gradient at 6.29:1 and above. The 0.4.0, 0.3.0, and
one-file walk-throughs (13, 26, 37 checks) passed again with the new markup.

For the side-bar layout (unreleased, 2026-11-04), 152 checks passed in headless Edge
(Playwright) at 1440 x 900, 1024 x 768, and 390 x 844 pixels in both themes: the three
landmarks and one `h1`; every visible control named; no horizontal scrolling with and without
results and with the side bar folded; the previous-step button disabled at step 1 and the
next-step button at step 6; the next-step button marking step 2; choosing a file moving the
mark to step 3 and cleaning to step 6; a clicked step staying marked; folding to a 56-pixel
rail, remembered after reloading, and unfolding; the side panel right of the main column at
1440 and under it at 1024; at 390 the overlay opening with focus on its toggle and the rest of
the page inert, Tab and Shift+Tab staying inside, Escape closing it with focus back on the
opening button, and a click beside it closing it; the Settings link opening More settings;
the whole workflow (file, profile, check, preview, save buttons enabled); the theme switch
and the Quit dialog from the side bar; the skip link as the first Tab stop, leading to the
main column. Lowest measured contrast of the new or moved colors: text 5.22:1 (dark) and
4.74:1 (light, the "Offline & local" pill), icons 6.55:1 (dark) and 5.58:1 (light). No
external request and no script error. The first run found that the overlay could not take
focus while it was still hidden; it is now visible as soon as it opens.

For the input card and step area (1.0.0, 2026-11-04), 218 checks passed in headless
Edge at the same three sizes in both themes, and the 152 side-bar checks passed again with
their expectations updated to the new marking (2 after reading, 5 after cleaning). New checks:
the start state (title, "No file chosen", only step 1, the size limit, the primary button
disabled); separator chips with arrow keys and a visible focus ring; reading a file showing
step 2 with the file name as title and breadcrumb; a click on a step not scrolling the page;
**Check** showing step 4, **Preview cleaning** step 5, **Save** step 6 with focus on Save
cleaned CSV; a rule change and a display-limit change keeping step 3; a separator change
reading again and showing step 2; **Other…** encoding showing its field; switching to several
files going back to step 1; three files titled "3 files with the same rules"; the file menu
listing them and "Add files…", focus on its first item, Escape returning focus, the arrow
keys and Enter previewing the second file; batch check and cleaning showing steps 4 and 5; no
horizontal scrolling. Lowest contrast of the new colors: text 4.8:1 (dark, unselected
separator and mode chips) and 5.17:1 (light, the size-limit note); icons 8.1:1 (dark) and
11.39:1 (light); white on the primary button 4.53:1 (dark) and 4.51:1 (light).
The run found two faults, both fixed: a press of the primary button was lost when a field that
reads the file again lost focus to it, and a new separator did not bring back step 2 when
results of the earlier reading were still present for a moment.

For the dark side-bar colors (1.0.0, 2026-11-04), 46 checks passed in headless Edge in
the dark theme at 1440, 1024 (side bar folded and unfolded), and 390 pixels (overlay open):
side bar #1F1F1F, page #191919, a #303030 line beside the side bar, above its bottom block,
and under the top bar at 390 pixels. Lowest contrast: text 4.8:1 (unselected chips on a
card) and 6.09:1 on the page itself, icons 6.08:1, focus ring 3.64:1 on the side bar and
3.88:1 on the page. The side-bar and input-card walk-throughs passed again in both themes.

For the side-bar sections, the side panel, and the accessibility pass (1.0.0, 2026-11-04),
421 checks passed in headless Edge in both themes at 1440, 1024, and 390 pixels, and the
earlier walk-throughs (156 shell, 218 input-card, 47 dark-color checks) passed again. New
checks: landmarks `nav`/`main`/`aside` and the `header` bar; every ARIA id reference resolves
and every `aria-controls` button states `aria-expanded`; every visible control named; the
whole page in Tab order (skip link, side bar or top bar, main column, side panel) with a
visible focus ring at every stop; the skip link moving focus into `main`; the session list
empty with its note, then one file with its row count and status (not checked, then problems
found or no problems, icon and words agreeing); the panel defaults, **Load** opening the
profile file chooser, the profile name, the column count, and the keys after loading; Find
opening with focus in its field, filtering the problems of step 4 and the column rules of
step 3 by name, saying how many rows match, Escape emptying and then closing it (the overlay
staying open at 390 pixels), and **Show all rows**; **Add** opening "More settings" at the
combined-key list, **Edit** (Output) focusing the output separator and the Output row
following a change, **Edit** (Columns) focusing the first rule that Find shows; three files
with a status each, a click on one showing its details while the other results stay; **New
check** asking first (focus on **Keep working**, Escape returning focus to New check), then
starting over (no files, default title, step 1, one-file mode, focus on the file field); the
folded side bar hiding the session list and **Find** unfolding it; with reduced motion no
side-bar slide, pulse, or icon turn; no horizontal scrolling. Lowest contrast of the new
colors: text 5.12:1 (light, **Show all rows**) and 5.17:1 (light, the session note); icons
4.82:1 (light, the "fine" state icon). These checks and the screenshots found four faults,
all fixed: the grey meta text of a session row would have been 4.08:1 on the dark hover color
(now on `--subtle`), the breadcrumb file button had no name before the script ran, **Edit**
(Columns) focused a rule row that Find had hidden, and the session list marked the previewed
file instead of the file whose details were open.

For the small logo mark and the removed style tokens (1.0.1, 2026-11-04), 58 checks passed in
headless Chrome 156 in both themes at 1440, 1024, and 390 pixels, and the earlier
walk-throughs (421 side-bar sections, 156 shell, 218 input-card, 47 dark-color checks) passed
again in the same browser. New checks: both logo images and the page icon load
`logo-mark.png` (64 x 64), keep `alt=""` and their width and height, and show at 28 pixels in
the side bar (also folded and in the overlay at 390 pixels) and 24 pixels in the top bar;
`--header`, `--status-bg`, and `--z-sticky` are undefined; a check and a preview of
`transactions_fixable.csv` run without horizontal scrolling, requests to other hosts, or
script errors. The mark's white document has 19:1 contrast on its black square; the square
itself has 17:1 against the Light+ side bar but only 1.15:1 against the dark side bar
(#1F1F1F), where the document, not the square's outline, carries the mark, as with the full
logo before.

For **How to use** and the removed background layer (1.1.0, 2026-11-04), 192 checks passed
in headless Chrome 156 in both themes at 1440, 1024, and 390 pixels, and the earlier
walk-throughs (58 logo-mark, 421 side-bar sections, 156 shell, 218 input-card, 47 dark-color
checks) passed again in the same browser. New checks: the guide is closed on a first visit
and its summary row spans the panel without the browser's marker; Tab from **Switch**
reaches it with a visible 3-pixel focus ring, Enter opens it, Space closes it; it stays open
or closed after a reload (`datakrit-howto`); with storage blocked the page has no errors and
the guide still opens; the chevron turns 180 degrees when open, at once with reduced motion;
opening it leaves the panel's width and position and the main column unchanged, the panel
only grows downward (at 1440 x 900 it scrolls on its own and its footer stays reachable);
each of the six step names shows its step and marks it in the step navigation, with a file
loaded; no horizontal scrolling, no requests to other hosts, no script errors. Contrast of
the new color pairs (on the panel `#1F1F1F` / `#FFFFFF`; hover `#2B2B2B` / `#F3F3F3`): caption
text and chevron 6.08:1 (dark) and 6.19:1 (light), on hover 8.82:1 and 11.39:1; step text
and tip 6.08:1 and 6.19:1; step links 6.65:1 and 5.68:1; focus ring 3.64:1 and 3.35:1.
Screenshots of both themes with and without text, before and after removing the background
layer, have the same background colors; the only differences are anti-aliasing (text is now
drawn with subpixel instead of grayscale smoothing, edges of rounded corners differ by at
most 7 of 255).

For the focus rings after a mouse click (1.1.1, 2026-11-04), 67 checks passed in
headless Chrome 156 in both themes at 1440, 1024, and 390 pixels, and the earlier
walk-throughs (192 guide, 58 logo-mark, 421 side-bar sections, 156 shell, 218 input-card,
47 dark-color checks) passed again. New checks: a mouse click on **Encoding** (open and
closed again), on **+** with a file chosen, on **Semicolon**, and on a list of step 3 draws
no focus ring and no glow, and the file card keeps its border; the chosen separator keeps its
ring; Tab to the file field, a separator, and **Encoding** shows the 3-pixel ring (and the
glow on the list). Chrome counts a list opened with the mouse as keyboard focus
(`:focus-visible`), which is why the page remembers whether it was last used with a pointer
or the keyboard.

For the chevron of the lists (1.1.1, 2026-11-04), 107 checks passed in headless Chrome
156 in both themes at 1440, 1024, and 390 pixels, and the earlier walk-throughs (67 focus,
192 guide, 58 logo-mark, 421 side-bar sections, 156 shell, 218 input-card, 47 dark-color
checks) passed again. New checks: every shown single-choice list, on the start page and in
step 3 with number and date rules and "More settings" open, has no browser arrow and the
chevron 12 to 14 pixels from its right edge, centred, with the text stopping before it; a
click opens **Encoding** and the chevron turns 180 degrees (150 ms; at once with reduced
motion) and turns back when the list closes; the arrow keys still change the encoding; the
chevron fades with a disabled list; the combined-key list keeps its box; no horizontal
scrolling. Chevron contrast: 4.8:1 on the dark list background (#313131) and 6.19:1 on the
light one (#FFFFFF). The date list of a column rule now has room for
"Like the file (YYYY-MM-DD)" (it was cut off by a few pixels before).

For the thin scroll bars (1.1.1, 2026-11-04), 19 checks passed in headless Chrome 156 with
its scroll bars shown (`--hide-scrollbars` removed): in a 1440 x 460 window with the guide
open, the page, the side panel, and the side bar each scroll with a 6-pixel bar; at 390
pixels the rule table scrolls sideways with a 6-pixel bar and the page does not. Thumb
contrast: dark #6E6E6E 3.23:1 on the panel and side bar (#1F1F1F) and 3.45:1 on the page
(#191919); light #8A8A8A 3.45:1 on the panel (#FFFFFF) and 3.11:1 on the page and side bar
(#F3F3F3); on hover 4.47 to 5.10:1.

`datakrit update --check` was run once against the real GitHub API (release 0.3.0): the wheel
and its digest were found and matched the published SHA-256. pip was shown to refuse a wheel
URL whose `#sha256=` fragment does not match and to accept the right one.

The update switch of 1.2.0 (2026-11-05) is recorded in this file as of the `v1.2.0` tag.

For 2.0.0 (2026-11-05), all walk-throughs passed again in headless Chrome at 1440, 1024, and
390 pixels in both themes (421 side-bar sections, 58 logo-mark, 192 guide, 156 shell, 218
input-card, 47 dark-color, 67 focus, 107 list, 19 scroll-bar checks), with no page errors.
The page title, side bar, "About this page", dialogs, and version chip show Datakrit; the
page icon and both side-bar marks load the new `logo-mark.png` (64 x 64) and show at 28
pixels in the side bar and 24 pixels in the narrow top bar. The mark's dark square (#1A1A1A)
measures 1.06:1 against the dark side bar (#1F1F1F) and 15.68:1 against the Light+ side bar
(#F3F3F3); on the dark side bar the white table and magnifier carry the mark (17.40:1 on the
square). The README screenshots were retaken. With the published 1.2.0 wheel and the built
2.0.0 wheel (offline, shortcuts in a folder), the 1.2.0 update, started as its Update
shortcut starts it, installed Datakrit 2.0.0, replaced the two old shortcuts with Datakrit's, removed the old
package, and left none of its files behind.

For 2.1.0 (2026-11-05) the interface did not change. The page was checked once more in each
theme at 1440 x 900, served by the built Windows app (`Datakrit.exe` from the local build,
started in smoke mode): the example file `transactions_fixable.csv` with the profile
`transactions-id.toml`, **Check**, and **Preview cleaning** showed "Ready to save: 4 rows, 9
values changed, 0 rows removed" in both themes, the page title and side bar showed 2.1.0, no
console errors or failed requests, no horizontal scrolling, and no content security policy
violation when the page loaded with the policy enforced. Quit through the page's API ended
the app with exit code 0.

These were automated walk-throughs by the maintainer's tooling, not tests with users or with
assistive technology; see [docs/USER_TESTING.md](docs/USER_TESTING.md).

## Manual checks before a release

See [docs/RELEASE.md](docs/RELEASE.md): CI green on the exact commit (Linux and Windows,
Python 3.11 and 3.15), `python -m build`, `python -m twine check --strict dist/*`,
`python scripts/smoke_dist.py dist`, the Windows app built and smoke-tested from the tag
(`packaging/windows/smoke_app.py` on the downloaded zip, with its SHA-256), the README
commands run from the tagged source, and after publishing: `pip install datakrit==X.Y.Z`
from PyPI in a fresh environment, `datakrit --version`, `datakrit update --check`, and the
SHA-256 of the wheel from PyPI compared with the release asset.

Not automated: a double-click on `Datakrit.exe` on a clean Windows computer, how
SmartScreen reacts to the unsigned app, and how antivirus programs react to it.
