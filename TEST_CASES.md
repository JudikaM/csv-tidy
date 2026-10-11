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
| AC-11 | Invalid dates, leap years, explicit formats, no guessing, invalid directives | `unit/test_formats.py`: `test_dates_follow_the_configured_format`, `test_invalid_dates_are_rejected`, `test_date_formatting_and_padding`, `test_invalid_date_directives_are_rejected`; `unit/test_validation.py`: `test_invalid_number_and_date_messages` |
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

## Regression tests

`tests/integration/test_regressions.py` covers defects found by the audit of commit
`e1e4a63`. Each test failed on that commit and passes now.

| ID | Defect | Related criteria | Tests |
|----|--------|------------------|-------|
| R1 | A value that fails its source format but looks valid in the output format was marked resolved | AC-09, AC-11, AC-12 | `test_r1_*` (numbers, dates, trim-then-parse, unchanged valid values, removed records) |
| R2 | Export after a working-directory change could overwrite the input CSV/profile | AC-17, AC-27 | `test_r2_export_after_cwd_change_cannot_overwrite_inputs` |
| R3 | Normalized values longer than `max_field_chars` produced an unreadable export | AC-22, AC-23, AC-24 | `test_r3_expanded_output_beyond_field_limit_blocks_export`, `test_r3_chain_stays_valid_when_the_limit_allows_expansion` |
| R4 | A destination created during the write was replaced without `--overwrite` | AC-19, AC-20 | `test_r4_destination_created_during_finalization_is_not_clobbered` |
| R5 | Binary/text-to-text codecs were accepted and crashed | AC-16 | `test_r5_non_text_codecs_are_configuration_errors`, `test_r5_text_encodings_still_work` |
| R6 | Directly constructed `Profile`/`ColumnSpec` objects skipped validation | AC-16, AC-25 | `test_r6_direct_profile_objects_are_validated`, `test_r6_valid_direct_profile_is_supported`, `test_r6_override_lists_must_be_sequences` |
| R7 | A failed `--report` write was not reflected in the printed report | AC-21 | `test_r7_*` |
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

## Manual checks before a release

See [docs/RELEASE.md](docs/RELEASE.md): CI green on the exact commit (Linux and Windows,
Python 3.11 and 3.15), `python -m build`, `python scripts/smoke_dist.py dist`, and the
README commands run from the tagged source.
