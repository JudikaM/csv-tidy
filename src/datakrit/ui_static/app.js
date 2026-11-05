"use strict";
/* Datakrit local interface. All file contents are placed in the page with textContent, never
   as HTML. Every result comes from the local datakrit process; this script validates nothing. */

const $ = (id) => document.getElementById(id);
const meta = (name) => document.querySelector(`meta[name="${name}"]`).content;
const TOKEN = meta("datakrit-token");
const MAX_FILE_MB = Number(meta("datakrit-max-file-mb")) || 200;
const KNOWN_ENCODINGS = ["utf-8", "cp1252", "latin-1", "utf-16"];
const NUMBER_LABELS = { canonical: "1250.50", id: "1.250,50", us: "1,250.50" };
/* Common numeric date formats, shown with 31 December 2026 as the example. */
const DATE_FORMATS = [
  ["YYYY-MM-DD", "2026-12-31"],
  ["DD/MM/YYYY", "31/12/2026"],
  ["MM/DD/YYYY", "12/31/2026"],
  ["DD-MM-YYYY", "31-12-2026"],
  ["DD.MM.YYYY", "31.12.2026"],
  ["YYYY/MM/DD", "2026/12/31"],
  ["YYYYMMDD", "20261231"],
  ["D/M/YYYY", "31/12/2026, also 1/2/2026"],
  ["M/D/YYYY", "12/31/2026, also 2/1/2026"],
];
const PING_SECONDS = 60;

/* Chrome counts a list (<select>) opened with the mouse as keyboard focus. Remember how the
   page was used last, so that app.css draws the list's focus ring for the keyboard only. */
document.addEventListener("pointerdown", () => { document.documentElement.dataset.input = "pointer"; }, true);
document.addEventListener("keydown", () => { document.documentElement.dataset.input = "keyboard"; }, true);

const DEFAULT_LIMITS = { max_details: 200, max_examples: 200, preview_rows: 50 };
const LIMIT_RANGES = { max_details: [0, 10000], max_examples: [0, 10000], preview_rows: [1, 1000] };
const STATUS_LABELS = {
  ready: "Ready",
  blocked: "Blocked",
  incomplete: "Not fully read",
  failed: "Failed",
  valid: "No problems",
  invalid: "Problems found",
};

const state = {
  mode: "single", // "single" or "batch"
  file: null, // {id, name, size}: the file in the preview (in batch mode, one of state.files)
  files: [], // batch mode: every chosen file
  batch: null, // {id, action, report, files, profile, limits}
  detail: null, // {fileId, name, data} of the batch file whose details are open
  header: [],
  preview: null,
  columns: new Map(), // name -> rule
  keys: [], // combined keys (two or more columns)
  profileName: null,
  check: null, // {id, report, profile, limits}
  clean: null, // {id, data, profile, limits}
  pending: null, // AbortController of the running request
  queued: false, // the primary button was pressed while a request was running
  cleared: false, // results were dropped since the last run
  restart: false, // New check cancelled the running request: no "Cancelled" message
  rows: new Map(), // file id -> data rows, once the file was read
  stopped: false,
};

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === false || value === null || value === undefined) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

const count = (n, noun, plural) => `${n.toLocaleString("en-US")} ${n === 1 ? noun : plural || noun + "s"}`;

/* A value with its leading and trailing whitespace made visible. */
function valueNode(value) {
  if (value === null || value === undefined) return el("span", { class: "none", text: "(none)" });
  if (value === "") return el("span", { class: "none", text: "(empty)" });
  const lead = value.match(/^[ \t]*/)[0];
  const rest = value.slice(lead.length);
  const trail = rest.match(/[ \t]*$/)[0];
  const middle = rest.slice(0, rest.length - trail.length);
  const mark = (text) =>
    text
      ? el("span", { class: "ws", title: "space or tab at the edge of the value" }, text.replace(/ /g, "·").replace(/\t/g, "→"))
      : null;
  return el("code", { class: "val" }, mark(lead), middle, mark(trail));
}

/* ------------------------------------------------------------------ status and requests */

function setStatus(kind, main, next) {
  $("status").dataset.kind = kind;
  $("status-main").textContent = main;
  $("status-next").textContent = next ? `Next: ${next}` : "";
}

function setBusy(on) {
  $("busy").hidden = !on;
  $("cancel").hidden = !on;
  for (const id of ["check-result", "clean-result", "preview"]) $(id).setAttribute("aria-busy", String(on));
  for (const control of document.querySelectorAll("#batch-files button, #preview-pick")) control.disabled = on;
  refreshButtons();
}

async function request(path, options) {
  const response = await fetch(path, {
    method: "POST",
    ...options,
    headers: { "X-Datakrit-Token": TOKEN, ...(options.headers || {}) },
  });
  if (response.ok) return response;
  let message = `The request failed (${response.status}).`;
  try {
    message = (await response.json()).error || message;
  } catch (error) {
    /* keep the generic message */
  }
  throw new Error(message);
}

const postJson = (path, body, signal) =>
  request(path, { body: JSON.stringify(body), headers: { "Content-Type": "application/json" }, signal });

/* Run one operation at a time, with a loading state and a working Cancel button. */
async function run(working, action) {
  if (state.pending || state.stopped) return;
  state.pending = new AbortController();
  state.cleared = false;
  setStatus("idle", working, "please wait; large files take longer. You can cancel.");
  setBusy(true);
  let done = false;
  try {
    await action(state.pending.signal);
    done = true;
  } catch (error) {
    if (error.name === "AbortError") {
      if (!state.restart) setStatus("warn", "Cancelled. Nothing was changed or saved.", "run the step again when you are ready.");
    } else if (error instanceof TypeError) {
      setStatus("bad", "Datakrit is not running any more.", "start it again from the Datakrit icon (it stops by itself after a while without an open page). Your files were not changed.");
    } else {
      setStatus("bad", error.message, "correct this, then try again.");
    }
  } finally {
    state.pending = null;
    state.restart = false;
    const queued = state.queued;
    state.queued = false;
    setBusy(false);
    /* The primary button was pressed while this ran (for example, a field that lost focus
       to the button read the file again): do it now, unless this failed or was cancelled. */
    if (queued && done && !state.stopped) primaryAction();
  }
}

/* ------------------------------------------------------------------ rules (step 3) */

const defaultRule = () => ({
  type: "text",
  required: false,
  numberFormat: "",
  dateFormat: "",
  unique: false,
  trim: false,
  normalize: false,
  neutralize: false,
});

function syncColumns() {
  const next = new Map();
  for (const name of state.header) next.set(name, state.columns.get(name) || defaultRule());
  for (const [name, rule] of state.columns) {
    if (!next.has(name) && rule.fromProfile) next.set(name, rule);
  }
  state.columns = next;
  const names = new Set(next.keys());
  state.keys = state.keys.filter((key) => key.every((name) => names.has(name)));
}

function currentEncoding() {
  const chosen = $("encoding").value;
  return chosen === "other" ? $("encoding-other").value.trim() : chosen;
}

const currentDelimiter = () => document.querySelector('input[name="delimiter"]:checked').value;

function wholeNumber(id, label, low, high) {
  const raw = $(id).value.trim();
  if (raw === "") return null;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < low || value > high) {
    $(id).setAttribute("aria-invalid", "true");
    throw new Error(`${label} must be a whole number from ${low.toLocaleString("en-US")} to ${high.toLocaleString("en-US")}.`);
  }
  $(id).removeAttribute("aria-invalid");
  return value;
}

/* The longest allowed value; null keeps the default (131072). */
const maxFieldChars = () => wholeNumber("max-field", "Longest allowed value", 1, 100000000);

function currentLimits() {
  const limits = { ...DEFAULT_LIMITS };
  for (const [name, id, label] of [
    ["max_details", "limit-details", "Problems listed"],
    ["max_examples", "limit-examples", "Changed values listed"],
    ["preview_rows", "limit-rows", "Rows shown in previews"],
  ]) {
    const value = wholeNumber(id, label, ...LIMIT_RANGES[name]);
    if (value !== null) limits[name] = value;
  }
  return limits;
}

function buildProfile() {
  const source = {
    delimiter: currentDelimiter(),
    encoding: currentEncoding(),
    number_format: $("src-number").value,
    date_format: dateValue("src-date") || "YYYY-MM-DD",
  };
  const longest = maxFieldChars();
  if (longest !== null) source.max_field_chars = longest;
  const output = { line_ending: $("line-ending").value };
  if ($("out-number").value) output.number_format = $("out-number").value;
  if (dateValue("out-date")) output.date_format = dateValue("out-date");
  if ($("out-delimiter").value) output.delimiter = $("out-delimiter").value;
  if ($("out-encoding").value.trim()) output.encoding = $("out-encoding").value.trim();
  const columns = {};
  const keys = [];
  const trim = [];
  const normalize = [];
  const neutralize = [];
  for (const [name, rule] of state.columns) {
    const spec = { type: rule.type, required: rule.required };
    if (rule.type === "decimal" && rule.numberFormat) spec.number_format = rule.numberFormat;
    if (rule.type === "date" && rule.dateFormat) spec.date_format = rule.dateFormat;
    columns[name] = spec;
    if (rule.unique) keys.push([name]);
    if (rule.trim) trim.push(name);
    if (rule.normalize && rule.type !== "text") normalize.push(name);
    if (rule.neutralize && rule.type === "text") neutralize.push(name);
  }
  const transform = { trim, normalize, deduplicate: $("dedupe").value };
  // Only when used, so that saved profiles stay readable by earlier versions.
  if (neutralize.length) transform.neutralize_formulas = neutralize;
  return {
    schema_version: 1,
    source,
    output,
    columns,
    duplicates: { rows: $("dup-rows").value, keys: [...keys, ...state.keys] },
    transform,
  };
}

function applyProfile(profile, name) {
  const source = profile.source || {};
  const output = profile.output || {};
  let reread = false;
  if (source.delimiter && source.delimiter !== currentDelimiter()) {
    for (const radio of document.querySelectorAll('input[name="delimiter"]')) {
      radio.checked = radio.value === source.delimiter;
    }
    reread = true;
  }
  if (source.encoding && source.encoding !== currentEncoding()) {
    setEncoding(source.encoding);
    reread = true;
  }
  $("src-number").value = source.number_format || "canonical";
  setDate("src-date", source.date_format || "YYYY-MM-DD");
  if (String(source.max_field_chars || "") !== $("max-field").value.trim()) reread = true;
  $("max-field").value = source.max_field_chars || "";
  $("out-number").value = output.number_format || "";
  setDate("out-date", output.date_format || "");
  $("out-delimiter").value = output.delimiter || "";
  $("out-encoding").value = output.encoding || "";
  $("line-ending").value = output.line_ending || "crlf";
  const duplicates = profile.duplicates || {};
  const transform = profile.transform || {};
  $("dup-rows").value = duplicates.rows || "warn";
  $("dedupe").value = transform.deduplicate || "off";

  const columns = new Map();
  const rule = (column) => {
    if (!columns.has(column)) columns.set(column, { ...defaultRule(), fromProfile: true });
    return columns.get(column);
  };
  for (const [column, spec] of Object.entries(profile.columns || {})) {
    Object.assign(rule(column), {
      type: spec.type || "text",
      required: Boolean(spec.required),
      numberFormat: spec.number_format || "",
      dateFormat: spec.date_format || "",
    });
  }
  for (const column of transform.trim || []) rule(column).trim = true;
  for (const column of transform.normalize || []) rule(column).normalize = true;
  for (const column of transform.neutralize_formulas || []) rule(column).neutralize = true;
  state.keys = [];
  for (const key of duplicates.keys || []) {
    if (key.length === 1) rule(key[0]).unique = true;
    else {
      key.forEach(rule);
      state.keys.push([...key]);
    }
  }
  state.columns = columns;
  state.profileName = name;
  syncColumns();
  return reread;
}

function setEncoding(encoding) {
  if (KNOWN_ENCODINGS.includes(encoding)) {
    $("encoding").value = encoding;
  } else {
    $("encoding").value = "other";
    $("encoding-other").value = encoding;
  }
  $("encoding-other-wrap").hidden = $("encoding").value !== "other";
}

function renderRules() {
  const ready = state.header.length > 0 || state.columns.size > 0;
  $("rules").hidden = !ready;
  $("rules-empty").hidden = ready;
  if (!ready) return;
  const active = document.activeElement && document.activeElement.id;
  const body = $("columns-body");
  body.replaceChildren();
  const inFile = new Set(state.header);
  const fileNumber = NUMBER_LABELS[$("src-number").value];
  const fileDate = dateValue("src-date") || "YYYY-MM-DD";
  let index = 0;
  for (const [name, rule] of state.columns) {
    const id = (field) => `col-${index}-${field}`;
    const typed = rule.type !== "text";
    const type = el(
      "select",
      { id: id("type"), "aria-label": `What column ${name} contains`, "data-field": "type" },
      el("option", { value: "text", text: "Text (kept exactly)" }),
      el("option", { value: "decimal", text: "Number" }),
      el("option", { value: "date", text: "Date" })
    );
    type.value = rule.type;
    let format = el("span", { class: "none", text: "as is" });
    if (rule.type === "decimal") {
      format = el(
        "select",
        { id: id("numberFormat"), "aria-label": `How numbers are written in column ${name}`, "data-field": "numberFormat" },
        el("option", { value: "", text: `Like the file (${fileNumber})` }),
        ...Object.entries(NUMBER_LABELS).map(([value, text]) => el("option", { value, text }))
      );
      format.value = rule.numberFormat;
      format = withChevron(format);
    } else if (rule.type === "date") {
      const known = DATE_FORMATS.some(([value]) => value === rule.dateFormat);
      const other = rule.dateOther || (rule.dateFormat && !known);
      const pick = el(
        "select",
        { id: id("dateChoice"), "aria-label": `How dates are written in column ${name}`, "data-field": "dateChoice" },
        el("option", { value: "", text: `Like the file (${fileDate})` }),
        ...DATE_FORMATS.map(([value, example]) => el("option", { value, text: `${example} (${value})` })),
        el("option", { value: "other", text: "Other…" })
      );
      pick.value = other ? "other" : rule.dateFormat;
      format = el("div", { class: "date-pick" }, withChevron(pick));
      if (other) {
        const custom = el("input", {
          type: "text",
          id: id("dateFormat"),
          "aria-label": `Other date format for column ${name}`,
          "data-field": "dateFormat",
          placeholder: "for example YYYY.MM.DD",
          autocomplete: "off",
          spellcheck: "false",
        });
        custom.value = rule.dateFormat;
        format.append(custom);
      }
    }
    const tick = (field, label, disabled) => {
      const box = el("input", { type: "checkbox", id: id(field), "aria-label": `${label}: column ${name}`, "data-field": field, disabled });
      box.checked = Boolean(rule[field]) && !disabled;
      return el("td", { class: "center" }, box);
    };
    const row = el(
      "tr",
      { "data-column": name },
      el(
        "th",
        { scope: "row" },
        el("code", { text: name }),
        inFile.has(name) ? null : el("span", { class: "missing", text: "Not in this file (from the loaded profile)" })
      ),
      el("td", null, withChevron(type)),
      el("td", null, format),
      tick("required", "Must not be empty"),
      tick("unique", "Must be unique"),
      tick("trim", "Trim spaces"),
      tick("normalize", "Convert format", !typed),
      tick("neutralize", "Protect formulas", typed)
    );
    if (!inFile.has(name)) {
      row.lastChild.append(
        el("button", { type: "button", class: "quiet", "data-remove": name, id: id("remove"), "aria-label": `Remove the rule for missing column ${name}` }, "Remove")
      );
    }
    body.append(row);
    index += 1;
  }
  const picker = $("key-columns");
  picker.replaceChildren(...[...state.columns.keys()].map((name) => el("option", { value: name, text: name })));
  $("keys").replaceChildren(
    ...state.keys.map((key, position) =>
      el(
        "li",
        null,
        key.join(" + "),
        el("button", { type: "button", "data-key": String(position), "aria-label": `Remove combined key ${key.join(" + ")}` }, "Remove")
      )
    )
  );
  if (state.keys.length === 0) $("keys").append(el("li", { class: "none", text: "None" }));
  if (active && $(active)) $(active).focus();
}

/* Any change to the file, its reading settings, or the rules makes earlier results stale. */
function invalidateResults(message) {
  if (state.check || state.clean || state.batch) state.cleared = true;
  state.check = null;
  state.clean = null;
  state.batch = null;
  state.detail = null;
  renderCheck();
  renderClean();
  refreshButtons();
  if (message && state.file) {
    setStatus(
      "warn",
      state.cleared ? `${message} Earlier results were cleared because they no longer match.` : message,
      state.header.length ? `select ${$("run-check").textContent} (step 4).` : "choose a file that can be read (the box at the top, and step 2)."
    );
  }
}

/* ------------------------------------------------------------------ rendering results */

function issuesTable(items, tag) {
  const ordered = [...items].sort((a, b) => (a.severity === "warning") - (b.severity === "warning"));
  const rows = ordered.map((issue) => {
    const where = [];
    if (issue.record !== null) where.push(`Record ${issue.record}`);
    if (issue.line_start !== null) {
      where.push(issue.line_end && issue.line_end !== issue.line_start ? `file lines ${issue.line_start}-${issue.line_end}` : `file line ${issue.line_start}`);
    }
    const label = tag || { error: "Error", fatal: "Stopped", warning: "Warning" }[issue.severity] || issue.severity;
    return el(
      "tr",
      null,
      el("td", null, el("span", { class: `tag ${tag ? tag.toLowerCase() : issue.severity}`, text: label })),
      el("td", null, where.join(", ") || "Whole file"),
      el("td", null, issue.column ? el("code", { text: issue.column }) : "—"),
      el("td", null, issue.message, issue.introduced ? el("div", { class: "note", text: "Created by a selected repair." }) : null),
      el("td", null, tag ? "Nothing; already handled." : plainSuggestion(issue))
    );
  });
  return el(
    "div",
    { class: "scroll", tabindex: "0", role: "region", "aria-label": "Problems" },
    el(
      "table",
      { class: "problems" },
      el("thead", null, el("tr", null, ...["Kind", "Where", "Column", "Problem", "What to do"].map((text) => el("th", { scope: "col", text })))),
      el("tbody", null, ...rows)
    )
  );
}

/* The page names its own controls instead of command-line options (issue.remedy comes
   from the same validation as the CLI; the CLI keeps its own wording). */
function plainSuggestion(issue) {
  const column = issue.column ? `"${issue.column}"` : "this column";
  switch (issue.remedy) {
    case "trim":
      return `Tick "Repair: trim spaces" for ${column} in step 3, or remove the spaces in your original file.`;
    case "number_format":
      return `Correct the value in your original file, or check "Written like" for ${column} in step 3 (for example 1.250,50 or 1,250.50).`;
    case "date_format":
      return `Correct the date in your original file, or check how dates in ${column} are written (step 3).`;
    case "deduplicate_rows":
      return 'If the copy is not wanted, choose "Remove rows identical to an earlier row" under "Duplicate rows in the cleaned copy" (step 3). The first row is kept.';
    case "deduplicate_keys":
      return 'Correct the repeated value in your original file, or choose "Also remove rows that repeat a unique value" (step 3) to keep only the first row.';
    case "delimiter":
      return 'Switch "Separator" in the box at the top.';
    case "encoding":
      return "Choose another encoding in the box at the top (files from older Excel versions are often Windows-1252), or save the file again as UTF-8.";
    case "quoting":
      return 'Check the quote marks (") in that row of your original file, and the separator in the box at the top.';
    case "max_field_chars":
      return 'Usually a quote mark (") is not closed in that row. Fix it in your original file, or raise "Longest allowed value" in More settings.';
    default:
      return issue.suggestion.replace(/\bin the source\b/g, "in your original file").replace(/\bthe source value\b/g, "the value in your original file");
  }
}

function fillDatePicks() {
  for (const prefix of ["src-date", "out-date"]) {
    const pick = $(`${prefix}-pick`);
    const first = prefix === "out-date" ? [el("option", { value: "", text: "Same as in this file" })] : [];
    pick.replaceChildren(
      ...first,
      ...DATE_FORMATS.map(([value, example]) => el("option", { value, text: `${example} (${value})` })),
      el("option", { value: "other", text: "Other…" })
    );
    setDate(prefix, pick.dataset.dateDefault);
  }
}

/* A date format from a list, or typed under "Other…". */
function dateValue(prefix) {
  const pick = $(`${prefix}-pick`);
  return pick.value === "other" ? $(prefix).value.trim() : pick.value;
}

function setDate(prefix, value) {
  const known = value === "" || DATE_FORMATS.some(([format]) => format === value);
  $(`${prefix}-pick`).value = known ? value : "other";
  $(prefix).value = known ? "" : value;
  $(`${prefix}-wrap`).hidden = known;
}

function dataTable(header, rows, label) {
  const head = el("tr", null, el("th", { scope: "col", class: "n", text: "Record" }), ...header.map((name) => el("th", { scope: "col", text: name })));
  const body = rows.map((row) =>
    el(
      "tr",
      null,
      el("td", { class: "n", text: String(row.record) }),
      ...row.fields.map((value, position) => el("td", { class: row.changed.includes(position) ? "changed" : null, text: value }))
    )
  );
  return el("table", { class: "data" }, el("caption", { class: "sr", text: label }), el("thead", null, head), el("tbody", null, ...body));
}

function coverageList(coverage) {
  const ruled = coverage.declared_columns.filter((c) => c.type !== "text" || c.required);
  const checked = ["the file structure (same number of fields in every row, usable column names)"];
  if (ruled.length) {
    checked.push(
      "values in " +
        ruled
          .map((c) => `${c.column} (${[c.type === "decimal" ? "number" : c.type, c.format, c.required ? "must not be empty" : null].filter(Boolean).join(", ")})`)
          .join("; ")
    );
  }
  for (const key of coverage.unique_keys) checked.push(`uniqueness of ${key.join(" + ")}`);
  if (coverage.duplicate_rows === "warn") checked.push("identical rows");
  const list = el("ul", { class: "coverage" }, el("li", null, el("b", { text: "Checked: " }), checked.join("; ") + "."));
  if (coverage.unchecked_columns.length) {
    list.append(
      el(
        "li",
        null,
        el("b", { text: "Not checked: " }),
        `values in ${count(coverage.unchecked_columns.length, "column")} without a rule (${coverage.unchecked_columns.join(", ")}). They are kept as text.`
      )
    );
  }
  return list;
}

function stopText(scan) {
  const fatal = scan.fatal_error;
  const where = fatal.line !== null ? ` at file line ${fatal.line}` : "";
  return `Reading stopped${where}: ${fatal.message}. Only the ${count(scan.data_records, "record")} before that point ${scan.data_records === 1 ? "was" : "were"} read.`;
}

function verdictBox(kind, title, detail) {
  return el("p", { class: "verdict", "data-kind": kind }, title, detail ? el("span", { text: detail }) : null);
}

function renderPreview() {
  const data = state.preview;
  $("preview").hidden = !data;
  $("preview-empty").hidden = Boolean(data);
  if (!data) return;
  const scan = data.report.scan;
  const facts = $("preview-facts");
  facts.replaceChildren(
    el("span", null, el("b", { text: state.file.name })),
    el("span", null, el("b", { text: scan.data_records.toLocaleString("en-US") }), " data rows"),
    el("span", null, el("b", { text: String(state.header.length) }), " columns"),
    el("span", null, el("b", { text: scan.physical_lines.toLocaleString("en-US") }), " lines in the file")
  );
  const issues = $("preview-issues");
  issues.replaceChildren();
  if (!scan.complete) issues.append(verdictBox("bad", "This file could not be read to the end.", stopText(scan)));
  const structural = data.report.issues.filter((issue) => issue.severity !== "fatal");
  if (structural.length) issues.append(issuesTable(structural));
  const table = $("preview-table");
  table.replaceChildren();
  if (data.header) {
    table.append(dataTable(data.header, data.rows, "First rows of the file"));
    if (data.rows_total > data.rows.length) {
      issues.append(el("p", { class: "note", text: `Showing the first ${data.rows.length} of ${data.rows_total.toLocaleString("en-US")} rows. Checks always use the whole file.` }));
    }
  }
  table.hidden = !data.header;
}

function renderCheck() {
  const box = $("check-result");
  box.replaceChildren();
  const batch = state.mode === "batch" && state.batch && state.batch.action === "check";
  box.hidden = !(batch || state.check);
  if (batch) renderBatch(box);
  else if (state.check) fillCheck(box, state.check.report);
}

function fillCheck(box, report) {
  const summary = report.summary;
  const warnings = summary.warnings ? ` ${count(summary.warnings, "warning")} to review.` : "";
  const verdicts = {
    passed: ["ok", `No problems found by your rules.${warnings}`, null],
    passed_structure_only: [
      "warn",
      `The file structure is fine, but no values were checked.${warnings}`,
      'No column has a rule yet. In step 3, choose Number or Date for the columns that hold them, or tick "Must not be empty" or "Must be unique".',
    ],
    failed: ["bad", `${count(summary.errors, "problem")} found in the file.${warnings}`, null],
    incomplete: ["bad", "The file could not be read to the end.", report.scan.complete ? null : stopText(report.scan)],
  };
  box.append(verdictBox(...verdicts[report.verdict.state]));
  box.append(
    el(
      "p",
      { class: "facts" },
      el("span", null, el("b", { text: report.scan.data_records.toLocaleString("en-US") }), " rows checked"),
      el("span", null, el("b", { text: String(summary.errors) }), " problems"),
      el("span", null, el("b", { text: String(summary.warnings) }), " warnings")
    ),
    coverageList(report.coverage)
  );
  if (report.issues.length) {
    box.append(el("h3", { text: "Problems, most serious first" }), issuesTable(report.issues));
    if (report.details.truncated) {
      box.append(el("p", { class: "note", text: `Showing ${report.details.shown} of ${report.details.total} problems. The counts above are complete; the saved report has the same limit.` }));
    }
  }
}

function renderClean() {
  const box = $("clean-result");
  box.replaceChildren();
  const batch = state.mode === "batch" && state.batch && state.batch.action === "clean";
  box.hidden = !(batch || state.clean);
  if (batch) renderBatch(box);
  else if (state.clean) fillClean(box, state.clean.data);
}

function fillClean(box, data) {
  const report = data.report;
  const changes = report.changes;
  const out = report.output_issues;
  const source = report.source_issues;
  const status = report.summary.status;
  if (status === "ready") {
    const repaired = source.items.filter((i) => i.status === "resolved" && i.severity === "error").length;
    box.append(verdictBox("ok", "The cleaned copy has no problems and can be saved.", repaired ? `${count(repaired, "problem")} from the file ${repaired === 1 ? "was" : "were"} repaired by the repairs you ticked.` : null));
  } else if (status === "incomplete") {
    box.append(verdictBox("bad", "The file could not be read to the end, so nothing can be saved.", stopText(report.scan)));
  } else {
    box.append(verdictBox("bad", `Saving is blocked: ${count(report.summary.output_errors, "problem")} would remain in the cleaned copy.`, data.blocked_reason));
  }
  box.append(
    el(
      "p",
      { class: "facts" },
      el("span", null, el("b", { text: changes.output_records.toLocaleString("en-US") }), " rows in the cleaned copy"),
      el("span", null, el("b", { text: String(out.errors) }), " problems remaining"),
      el("span", null, el("b", { text: String(out.warnings) }), " warnings remaining"),
      el("span", null, el("b", { text: changes.changed_fields.toLocaleString("en-US") }), ` values changed (in ${count(changes.changed_records, "row")})`),
      el("span", null, el("b", { text: changes.removed_records.toLocaleString("en-US") }), " rows removed")
    )
  );
  const open = status === "incomplete" ? source.items : out.items;
  if (open.length) box.append(el("h3", { text: "Still to fix" }), issuesTable(open));

  box.append(el("h3", { text: "Values that change (before and after)" }));
  if (changes.examples.length) {
    box.append(
      el(
        "div",
        { class: "scroll", tabindex: "0", role: "region", "aria-label": "Values before and after" },
        el(
          "table",
          null,
          el("thead", null, el("tr", null, ...["Record", "File line", "Column", "Before", "After", "Repair"].map((text) => el("th", { scope: "col", text })))),
          el(
            "tbody",
            null,
            ...changes.examples.map((c) =>
              el(
                "tr",
                null,
                el("td", { class: "n", text: String(c.record) }),
                el("td", { class: "n", text: String(c.line_start) }),
                el("td", null, el("code", { text: c.column })),
                el("td", null, valueNode(c.before)),
                el("td", null, valueNode(c.after)),
                el("td", null, c.steps.map((s) => ({ trim: "trim spaces", normalize: "convert format", neutralize_formulas: "protect formulas" })[s] || s).join(", "))
              )
            )
          )
        )
      )
    );
    if (changes.changed_fields > changes.examples.length) {
      box.append(el("p", { class: "note", text: `Showing the first ${changes.examples.length} of ${changes.changed_fields.toLocaleString("en-US")} changed values.` }));
    }
  } else {
    box.append(el("p", { class: "note", text: status === "incomplete" ? "Nothing was changed." : "No value changes. Tick a repair in step 3 if values need trimming or converting." }));
  }
  if (changes.removed.length) {
    box.append(
      el("h3", { text: "Rows removed as duplicates" }),
      el(
        "ul",
        { class: "coverage" },
        ...changes.removed.map((r) => el("li", null, `Record ${r.record} (file line ${r.line_start}) repeats record ${r.kept_record}${r.key ? ` in ${r.key.join(" + ")}` : " exactly"}; record ${r.kept_record} is kept.`))
      )
    );
  }
  const handled = source.items.filter((i) => i.status === "resolved" || i.status === "removed");
  if (handled.length) {
    const fixed = handled.filter((i) => i.status === "resolved");
    const gone = handled.filter((i) => i.status === "removed");
    box.append(
      el(
        "details",
        null,
        el("summary", { text: `Problems from the file that are already handled (${handled.length})` }),
        fixed.length ? issuesTable(fixed, "Fixed") : null,
        gone.length ? issuesTable(gone, "Removed") : null
      )
    );
  }
  if (data.header && data.rows.length) {
    box.append(
      el("h3", { text: "The cleaned copy" }),
      el("p", { class: "note", text: `First ${data.rows.length} of ${data.rows_total.toLocaleString("en-US")} rows. Changed values are highlighted.` }),
      el("div", { class: "scroll", tabindex: "0", role: "region", "aria-label": "Cleaned copy" }, dataTable(data.header, data.rows, "First rows of the cleaned copy"))
    );
  }
}

/* One row per file with its status; partial failures are named with their reason. */
function renderBatch(box) {
  const { report, action } = state.batch;
  const totals = report.totals;
  const verb = action === "check" ? "checked" : "prepared";
  const notOk = totals.data_errors + totals.failed;
  if (!notOk) {
    const structure = report.files.some((f) => f.structure_only);
    box.append(
      verdictBox(
        structure ? "warn" : "ok",
        action === "check"
          ? `All ${count(totals.files, "file")} passed the check.`
          : `All ${count(totals.files, "file")} are ready to save.`,
        structure ? "Only the file structure was checked: no column has a rule yet (step 3)." : null
      )
    );
  } else {
    const parts = [];
    if (totals.data_errors) parts.push(`${totals.data_errors} with problems in the data`);
    if (totals.failed) parts.push(`${totals.failed} that could not be read or processed`);
    box.append(
      verdictBox(
        "bad",
        `${notOk} of ${count(totals.files, "file")} need attention: ${parts.join(", ")}.`,
        action === "clean"
          ? `The other ${count(totals.ok, "file")} ${totals.ok === 1 ? "is" : "are"} ready. Only ready files are saved as cleaned CSV; every file gets a report.`
          : "Open Details for the problems of a file."
      )
    );
  }
  const facts = [
    [totals.files, " files " + verb],
    [totals.ok, action === "check" ? " without problems" : " ready"],
    [totals.data_errors, " with data problems"],
    [totals.failed, " not processed"],
    [totals.data_records, " rows in total"],
  ];
  if (action === "clean") facts.push([totals.changed_fields, " values changed"], [totals.removed_records, " rows removed"]);
  box.append(el("p", { class: "facts" }, ...facts.map(([n, text]) => el("span", null, el("b", { text: n.toLocaleString("en-US") }), text))));

  const heads = ["File", "Result", "Rows", action === "check" ? "Problems" : "Problems left", "What happened", "Actions"];
  if (action === "clean") heads.splice(4, 0, "Values changed", "Rows removed");
  const rows = report.files.map((entry, index) => {
    const file = state.batch.files[index];
    let what = "";
    if (entry.error) what = entry.error;
    else if (entry.status === "blocked") what = `${count(entry.output_errors, "problem")} would remain, so this file is not saved.`;
    else if (entry.status === "invalid") what = `${count(entry.errors, "problem")} in the file.`;
    else if (entry.structure_only) what = "Only the structure was checked (no column rules).";
    else what = action === "check" ? "No problems found." : "Ready to save.";
    const actions = el(
      "div",
      { class: "row-actions" },
      el("button", { type: "button", "data-detail": String(file.file_id), "aria-label": `Show details of ${file.name}` }, "Details")
    );
    if (action === "clean" && entry.status === "ready") {
      actions.append(el("button", { type: "button", "data-save": String(file.file_id), "aria-label": `Save the cleaned copy of ${file.name}` }, "Save CSV"));
    }
    const cells = [
      el("th", { scope: "row" }, el("code", { text: entry.path })),
      el("td", null, el("span", { class: `tag ${entry.status}`, text: STATUS_LABELS[entry.status] || entry.status })),
      el("td", { class: "n", text: entry.data_records.toLocaleString("en-US") }),
      el("td", { class: "n", text: String(action === "check" ? entry.errors : entry.output_errors ?? 0) }),
    ];
    if (action === "clean") {
      cells.push(el("td", { class: "n", text: entry.changed_fields.toLocaleString("en-US") }), el("td", { class: "n", text: entry.removed_records.toLocaleString("en-US") }));
    }
    cells.push(el("td", null, what), el("td", null, actions));
    return el("tr", { class: state.detail && state.detail.fileId === file.file_id ? "current" : null }, ...cells);
  });
  box.append(
    el("h3", { text: "Result per file" }),
    el(
      "div",
      { class: "scroll", tabindex: "0", role: "region", "aria-label": "Result per file" },
      el("table", { class: "batch" }, el("thead", null, el("tr", null, ...heads.map((text) => el("th", { scope: "col", text })))), el("tbody", null, ...rows))
    )
  );
  if (state.detail) {
    const panel = el("section", { class: "detail", "aria-label": `Details of ${state.detail.name}` }, el("h3", { text: `Details: ${state.detail.name}` }));
    if (state.detail.data.action === "check") fillCheck(panel, state.detail.data.report);
    else fillClean(panel, state.detail.data);
    box.append(panel);
  }
}

function refreshButtons() {
  refreshLook();
  const busy = Boolean(state.pending) || state.stopped;
  const loaded = Boolean(state.file) && state.header.length > 0;
  $("run-check").disabled = busy || !loaded;
  $("run-clean").disabled = busy || !loaded;
  refreshPrimary(busy, loaded);
  const batchMode = state.mode === "batch";
  $("batch-actions").hidden = !batchMode;
  $("single-actions").hidden = batchMode;
  $("run-check").textContent = batchMode ? "Check all files" : "Check file";
  $("run-clean").textContent = batchMode ? "Preview cleaning of all files" : "Preview cleaning";
  for (const id of ["save-zip", "save-batch-summary", "save-batch-summary-json"]) $(id).disabled = busy || !state.batch;
  $("save-profile").disabled = busy || !loaded;
  if (batchMode) {
    const blocked = $("save-blocked");
    let reason = "";
    if (!state.files.length) reason = "";
    else if (!state.batch) reason = "Results can be saved after Check all files (step 4) or Preview cleaning of all files (step 5).";
    else if (state.batch.action === "check") reason = "The ZIP holds one report per file and the summary. Run Preview cleaning of all files to include cleaned CSV files.";
    else if (state.batch.report.totals.ok < state.batch.report.totals.files) {
      reason = `Only the ${count(state.batch.report.totals.ok, "file")} marked Ready ${state.batch.report.totals.ok === 1 ? "is" : "are"} saved as cleaned CSV. Files that need attention are included as reports only.`;
    }
    blocked.hidden = !reason;
    blocked.textContent = reason;
    blocked.className = "note";
    return;
  }
  const clean = state.clean;
  const ready = Boolean(clean) && clean.data.report.summary.export_ready;
  $("save-csv").disabled = busy || !ready;
  $("save-output-profile").disabled = busy || !ready;
  $("save-report").disabled = busy || !(clean || state.check);
  $("save-report-json").disabled = busy || !(clean || state.check);
  $("save-profile").disabled = busy || !loaded;
  const blocked = $("save-blocked");
  let reason = "";
  if (!state.file) reason = "";
  else if (!clean) reason = "The cleaned CSV can be saved after a preview (step 5) shows no remaining problems.";
  else if (!ready) reason = `The cleaned CSV cannot be saved yet. ${clean.data.blocked_reason || ""} You can still save the report.`;
  blocked.hidden = !reason;
  blocked.textContent = reason;
  blocked.className = clean && !ready ? "blocked" : "note";
}

/* ------------------------------------------------------------------ actions */

async function loadPreview(signal, lead) {
  const body = { file_id: state.file.id, delimiter: currentDelimiter(), encoding: currentEncoding(), limits: currentLimits() };
  const longest = maxFieldChars();
  if (longest !== null) body.max_field_chars = longest;
  const response = await postJson("/api/preview", body, signal);
  state.preview = await response.json();
  state.rows.set(state.file.id, state.preview.report.scan.data_records);
  state.header = state.preview.header ? [...new Set(state.preview.header)] : [];
  syncColumns();
  state.check = null;
  state.clean = null;
  state.batch = null;
  state.detail = null;
  renderBatchFiles();
  renderPreview();
  renderRules();
  renderCheck();
  renderClean();
  const scan = state.preview.report.scan;
  const errors = state.preview.report.summary.errors;
  const hint = state.preview.report.issues.find((issue) => issue.code === "possible_wrong_delimiter");
  if (!scan.complete) {
    setStatus("bad", "This file could not be read to the end.", "check the separator and the encoding in the box at the top, or repair the file. Details are in step 2.");
  } else if (hint) {
    setStatus("warn", "The file loaded as one wide column.", "switch the separator in the box at the top; the file probably uses the other one.");
  } else if (errors) {
    setStatus("bad", `${lead} The file has ${count(errors, "structure problem")}.`, "see step 2, then set the rules (step 3) and select Check file.");
  } else if (state.mode === "batch") {
    setStatus(
      "ok",
      `${lead} ${count(state.files.length, "file")} chosen; previewing ${state.file.name} (${count(scan.data_records, "row")}, ${count(state.header.length, "column")}).`,
      "set the rules in step 3 (or load a profile); they apply to every file. Then select Check all files."
    );
  } else {
    setStatus("ok", `${lead} ${count(scan.data_records, "row")}, ${count(state.header.length, "column")}.`, "confirm the preview, set the rules in step 3 (or load a profile), then select Check file.");
  }
}

function chooseFile() {
  if (state.mode === "batch") {
    chooseFiles();
    return;
  }
  const file = $("file").files[0];
  if (!file) return;
  if (file.size > MAX_FILE_MB * 1024 * 1024) {
    setStatus("bad", `This file is larger than ${MAX_FILE_MB} MB.`, "split the file, or start datakrit ui with a higher --max-file-mb.");
    return;
  }
  run(`Reading ${file.name}…`, async (signal) => {
    const response = await request("/api/file", {
      body: file,
      headers: { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name) },
      signal,
    });
    const stored = await response.json();
    state.file = { id: stored.file_id, name: stored.name, size: stored.size };
    state.preview = null;
    $("file-note").textContent = `Loaded: ${state.file.name} (${Math.max(1, Math.round(state.file.size / 1024)).toLocaleString("en-US")} KB). It is only read, never changed.`;
    await loadPreview(signal, "File loaded.");
  });
}

async function upload(file, append, signal) {
  const response = await request(append ? "/api/file?mode=append" : "/api/file", {
    body: file,
    headers: { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name) },
    signal,
  });
  const stored = await response.json();
  return { id: stored.file_id, name: stored.name, size: stored.size };
}

function chooseFiles() {
  const chosen = [...$("file").files];
  $("file").value = "";
  if (!chosen.length) return;
  const total = [...state.files, ...chosen].reduce((sum, f) => sum + f.size, 0);
  if (total > MAX_FILE_MB * 1024 * 1024) {
    setStatus("bad", `The chosen files together are larger than ${MAX_FILE_MB} MB.`, "process them in smaller groups, or start datakrit ui with a higher --max-file-mb.");
    return;
  }
  run(`Reading ${count(chosen.length, "file")}…`, async (signal) => {
    const failed = [];
    for (const file of chosen) {
      try {
        // The first file of a new selection replaces whatever one-file mode had loaded.
        state.files.push(await upload(file, state.files.length > 0, signal));
      } catch (error) {
        if (error.name === "AbortError") throw error;
        failed.push(`${file.name}: ${error.message}`);
      }
    }
    invalidateResults();
    if (!state.file && state.files.length) state.file = state.files[0];
    renderBatchFiles();
    if (state.file) await loadPreview(signal, `${count(chosen.length - failed.length, "file")} added.`);
    if (failed.length) setStatus("bad", `${count(failed.length, "file")} could not be added: ${failed.join("; ")}`, "the other files are kept. Fix or remove the file, then add it again.");
  });
}

function renderBatchFiles() {
  const batchMode = state.mode === "batch";
  $("batch-files-wrap").hidden = !batchMode || !state.files.length;
  $("preview-pick-wrap").hidden = !batchMode || state.files.length < 2;
  if (!batchMode) return;
  $("batch-files").replaceChildren(
    ...state.files.map((file) =>
      el(
        "tr",
        { class: state.file && state.file.id === file.id ? "current" : null },
        el("th", { scope: "row" }, el("code", { text: file.name }), state.file && state.file.id === file.id ? el("span", { class: "note", text: " (in the preview)" }) : null),
        el("td", { class: "n", text: `${Math.max(1, Math.round(file.size / 1024)).toLocaleString("en-US")} KB` }),
        el(
          "td",
          null,
          el(
            "div",
            { class: "row-actions" },
            el("button", { type: "button", "data-preview": String(file.id), "aria-label": `Preview ${file.name}` }, "Preview"),
            el("button", { type: "button", "data-remove-file": String(file.id), "aria-label": `Remove ${file.name} from the selection` }, "Remove")
          )
        )
      )
    )
  );
  $("preview-pick").replaceChildren(...state.files.map((file) => el("option", { value: String(file.id), text: file.name })));
  if (state.file) $("preview-pick").value = String(state.file.id);
  $("file-note").textContent = state.files.length
    ? `${count(state.files.length, "file")} chosen. Choose more files to add them. They are only read, never changed.`
    : "Choose one or more CSV files. They are only read, never changed.";
}

function previewBatchFile(id) {
  const file = state.files.find((f) => f.id === id);
  if (!file) return;
  state.file = file;
  run(`Reading ${file.name}…`, (signal) => loadPreview(signal, "Preview changed."));
}

function removeBatchFile(id) {
  run("Removing the file…", async (signal) => {
    await postJson("/api/file/remove", { file_id: id }, signal);
    state.files = state.files.filter((f) => f.id !== id);
    invalidateResults();
    if (state.file && state.file.id === id) {
      state.file = state.files[0] || null;
      state.preview = null;
      if (!state.file) {
        state.header = [];
        syncColumns();
      }
    }
    renderBatchFiles();
    if (state.file) await loadPreview(signal, "File removed.");
    else {
      renderPreview();
      renderRules();
      setStatus("idle", "No files chosen.", "choose the CSV files in the box at the top.");
    }
  });
}

function setMode(mode) {
  if (mode === state.mode) return;
  if (state.pending) state.pending.abort();
  state.mode = mode;
  state.file = null;
  state.files = [];
  state.preview = null;
  state.header = [];
  invalidateResults();
  $("file").multiple = mode === "batch";
  $("file").value = "";
  $("file-label").textContent = mode === "batch" ? "CSV files" : "CSV file";
  $("file-note").textContent = mode === "batch" ? "Choose one or more CSV files. They are only read, never changed." : "Your file is only read. It is never changed.";
  syncColumns();
  renderBatchFiles();
  renderPreview();
  renderRules();
  refreshButtons();
  setStatus(
    "idle",
    mode === "batch" ? "Several files: the same rules are applied to every file." : "One file at a time.",
    mode === "batch" ? "choose the CSV files in the box at the top (you can choose several at once)." : "choose a CSV file in the box at the top."
  );
}

function rereadFile(message) {
  if (!state.file) return;
  run("Reading the file again…", (signal) => loadPreview(signal, message));
}

function validateRulesLocally() {
  if ($("dedupe").value === "keys" && state.keys.length === 0 && ![...state.columns.values()].some((rule) => rule.unique)) {
    throw new Error('"Also remove rows that repeat a unique value" needs at least one column ticked "Must be unique" (step 3).');
  }
  if (!currentEncoding()) throw new Error("Type the name of the encoding under the box at the top.");
}

function runBatch(action) {
  run(action === "check" ? "Checking every file…" : "Preparing cleaned copies of every file…", async (signal) => {
    validateRulesLocally();
    const profile = buildProfile();
    const limits = currentLimits();
    const body = { action, file_ids: state.files.map((f) => f.id), profile, profile_name: state.profileName, limits };
    const response = await postJson("/api/batch", body, signal);
    const data = await response.json();
    state.batch = { id: data.batch_id, action, report: data.report, files: data.files, profile, limits };
    state.detail = null;
    renderCheck();
    renderClean();
    const t = data.report.totals;
    const problems = t.data_errors + t.failed;
    if (!problems) {
      setStatus(
        "ok",
        action === "check" ? `All ${count(t.files, "file")} passed the check.` : `All ${count(t.files, "file")} are ready to save.`,
        action === "check" ? "select Preview cleaning of all files (step 5)." : "save them as one ZIP in step 6, or each file with Save CSV."
      );
    } else {
      setStatus(
        "bad",
        `${problems} of ${count(t.files, "file")} need attention.`,
        action === "check"
          ? "open Details for each file marked in red. Fix the files or tick repairs in step 3, then check again."
          : `${count(t.ok, "file")} ${t.ok === 1 ? "is" : "are"} ready and can be saved now. For the others, open Details.`
      );
    }
    $(action === "check" ? "check-result" : "clean-result").scrollIntoView({ block: "nearest" });
  });
}

function showBatchDetail(fileId) {
  const file = state.batch.files.find((f) => f.file_id === fileId);
  run(`Loading the details of ${file.name}…`, async (signal) => {
    const body = { batch_id: state.batch.id, file_id: fileId, profile: state.batch.profile, limits: state.batch.limits };
    const response = await postJson("/api/batch/file", body, signal);
    state.detail = { fileId, name: file.name, data: await response.json() };
    renderCheck();
    renderClean();
    setStatus("idle", `Showing the details of ${file.name}.`, "read the problems and suggestions below the table.");
    const panel = document.querySelector(".detail");
    if (panel) panel.scrollIntoView({ block: "nearest" });
  });
}

function runCheck() {
  if (state.mode === "batch") {
    runBatch("check");
    return;
  }
  run("Checking the file…", async (signal) => {
    validateRulesLocally();
    const profile = buildProfile();
    const limits = currentLimits();
    const response = await postJson("/api/check", { file_id: state.file.id, profile, profile_name: state.profileName, limits }, signal);
    const data = await response.json();
    state.check = { id: data.result_id, report: data.report, profile, limits };
    renderCheck();
    const s = data.report.summary;
    const verdict = data.report.verdict.state;
    if (verdict === "incomplete") {
      setStatus("bad", "The file could not be read to the end.", "check the separator and encoding in the box at the top, or repair the file.");
    } else if (verdict === "failed") {
      setStatus("bad", `${count(s.errors, "problem")} found.`, "fix them in your original file, or tick a repair in step 3 and select Preview cleaning.");
    } else if (verdict === "passed_structure_only") {
      setStatus("warn", "Structure is fine, but no values were checked.", "give columns a rule in step 3 (Number, Date, Must not be empty), then check again.");
    } else {
      setStatus("ok", `No problems found.${s.warnings ? ` ${count(s.warnings, "warning")} to review.` : ""}`, "select Preview cleaning (step 5) to prepare a cleaned copy.");
    }
    $("check-result").scrollIntoView({ block: "nearest" });
  });
}

function runClean() {
  if (state.mode === "batch") {
    runBatch("clean");
    return;
  }
  run("Preparing the cleaned copy…", async (signal) => {
    validateRulesLocally();
    const profile = buildProfile();
    const limits = currentLimits();
    const response = await postJson("/api/clean", { file_id: state.file.id, profile, profile_name: state.profileName, limits }, signal);
    const data = await response.json();
    state.clean = { id: data.result_id, data, profile, limits };
    renderClean();
    const report = data.report;
    if (report.summary.status === "ready") {
      setStatus(
        "ok",
        `Ready to save: ${count(report.changes.output_records, "row")}, ${count(report.changes.changed_fields, "value")} changed, ${count(report.changes.removed_records, "row")} removed.`,
        "review the changes in step 5, then select Save cleaned CSV (step 6)."
      );
    } else if (report.summary.status === "incomplete") {
      setStatus("bad", "The file could not be read to the end; nothing can be saved.", "check the separator and encoding in the box at the top, or repair the file.");
    } else {
      setStatus("bad", `Saving is blocked: ${count(report.summary.output_errors, "problem")} remain.`, 'see "Still to fix" in step 5. Fix them in your original file or tick a repair in step 3, then preview again.');
    }
    $("clean-result").scrollIntoView({ block: "nearest" });
  });
}

async function saveResponse(response, what) {
  const name = decodeURIComponent(response.headers.get("X-File-Name") || "download");
  const url = URL.createObjectURL(await response.blob());
  const link = el("a", { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  setStatus("ok", `${what} saved as ${name}.`, "look in your browser's download folder. Your original file was not changed.");
  toast("Saved", name);
}

function download(kind, what) {
  run(`Saving ${what.toLowerCase()}…`, async (signal) => {
    const fromCheck = kind.startsWith("check-");
    const stored = fromCheck ? state.check : state.clean;
    const response = await postJson("/api/download", { result_id: stored.id, kind, profile: stored.profile, limits: stored.limits }, signal);
    await saveResponse(response, what);
  });
}

function downloadBatch(kind, what, fileId) {
  run(`Saving ${what.toLowerCase()}…`, async (signal) => {
    const body = { batch_id: state.batch.id, kind, profile: state.batch.profile, limits: state.batch.limits };
    if (fileId !== undefined) body.file_id = fileId;
    const response = await postJson("/api/download", body, signal);
    await saveResponse(response, what);
  });
}

function saveReport(json) {
  if (state.clean) download(json ? "report-json" : "report-text", "Report");
  else if (state.check) download(json ? "check-report-json" : "check-report-text", "Report");
}

function saveProfile() {
  run("Saving the profile…", async (signal) => {
    validateRulesLocally();
    const name = state.mode === "batch" && state.files.length > 1 ? "batch.csv" : state.file.name;
    const response = await postJson("/api/profile/toml", { profile: buildProfile(), file_name: name }, signal);
    await saveResponse(response, "Profile");
  });
}

function loadProfile() {
  const file = $("profile-file").files[0];
  if (!file) return;
  run(`Loading ${file.name}…`, async (signal) => {
    const text = await file.text();
    const response = await postJson("/api/profile/parse", { text, name: file.name }, signal);
    const data = await response.json();
    const reread = applyProfile(data.profile, data.name);
    $("profile-note").textContent = `Loaded rules from ${data.name}. You can still change anything below.`;
    renderRules();
    if (reread) {
      await loadPreview(signal, `Profile ${data.name} loaded; the file was read again with its separator and encoding.`);
    } else {
      invalidateResults();
      setStatus("ok", `Profile ${data.name} loaded.`, `review the rules in step 3, then select ${$("run-check").textContent}.`);
    }
  });
}

/* ------------------------------------------------------------------ events */

$("file").addEventListener("change", chooseFile);
for (const radio of document.querySelectorAll('input[name="delimiter"]')) {
  radio.addEventListener("change", () => rereadFile("Separator changed; the file was read again."));
}
$("encoding").addEventListener("change", () => {
  $("encoding-other-wrap").hidden = $("encoding").value !== "other";
  if ($("encoding").value === "other") $("encoding-other").focus();
  else rereadFile("Encoding changed; the file was read again.");
});
$("encoding-other").addEventListener("change", () => {
  if (currentEncoding()) rereadFile("Encoding changed; the file was read again.");
});

$("columns-body").addEventListener("change", (event) => {
  const field = event.target.dataset.field;
  const row = event.target.closest("tr");
  if (!field || !row) return;
  const rule = state.columns.get(row.dataset.column);
  if (field === "dateChoice") {
    rule.dateOther = event.target.value === "other";
    if (!rule.dateOther) rule.dateFormat = event.target.value;
  } else {
    rule[field] = event.target.type === "checkbox" ? event.target.checked : event.target.value.trim();
  }
  if (rule.type === "text") rule.normalize = false;
  else rule.neutralize = false;
  renderRules();
  invalidateResults("Rules changed.");
});
$("columns-body").addEventListener("click", (event) => {
  const name = event.target.dataset.remove;
  if (name === undefined) return;
  state.columns.delete(name);
  syncColumns();
  renderRules();
  invalidateResults("Rules changed.");
});
for (const radio of document.querySelectorAll('input[name="mode"]')) {
  radio.addEventListener("change", () => setMode(radio.value));
}
$("batch-files").addEventListener("click", (event) => {
  const preview = event.target.dataset.preview;
  const remove = event.target.dataset.removeFile;
  if (preview !== undefined) previewBatchFile(Number(preview));
  if (remove !== undefined) removeBatchFile(Number(remove));
});
$("preview-pick").addEventListener("change", () => previewBatchFile(Number($("preview-pick").value)));
for (const box of ["check-result", "clean-result"]) {
  $(box).addEventListener("click", (event) => {
    const detail = event.target.dataset.detail;
    const save = event.target.dataset.save;
    if (detail !== undefined) showBatchDetail(Number(detail));
    if (save !== undefined) {
      const file = state.batch.files.find((f) => f.file_id === Number(save));
      downloadBatch("batch-csv", `Cleaned copy of ${file.name}`, Number(save));
    }
  });
}
$("save-zip").addEventListener("click", () => downloadBatch("batch-zip", "All results"));
$("save-batch-summary").addEventListener("click", () => downloadBatch("batch-summary-text", "Summary"));
$("save-batch-summary-json").addEventListener("click", () => downloadBatch("batch-summary-json", "Summary"));
$("max-field").addEventListener("change", () => {
  try {
    maxFieldChars();
  } catch (error) {
    setStatus("bad", error.message, "correct the value in More settings.");
    return;
  }
  invalidateResults();
  rereadFile("Longest allowed value changed; the file was read again.");
});
for (const id of ["limit-details", "limit-examples", "limit-rows"]) {
  $(id).addEventListener("change", () => {
    try {
      currentLimits();
    } catch (error) {
      setStatus("bad", error.message, "correct the value in More settings.");
      return;
    }
    if (id === "limit-rows") {
      invalidateResults();
      rereadFile("Preview size changed; the file was read again.");
    } else invalidateResults("Detail limits changed.");
  });
}
for (const prefix of ["src-date", "out-date"]) {
  $(`${prefix}-pick`).addEventListener("change", () => {
    const other = $(`${prefix}-pick`).value === "other";
    $(`${prefix}-wrap`).hidden = !other;
    if (other) $(prefix).focus();
  });
}
for (const id of ["src-number", "src-date", "src-date-pick", "out-number", "out-date", "out-date-pick", "dedupe", "dup-rows", "out-delimiter", "out-encoding", "line-ending"]) {
  $(id).addEventListener("change", () => {
    renderRules();
    invalidateResults("Settings changed.");
  });
}
$("add-key").addEventListener("click", () => {
  const chosen = [...$("key-columns").selectedOptions].map((option) => option.value);
  if (chosen.length < 2) {
    setStatus("warn", "A combined key needs two or more columns.", 'pick several columns in the list, or tick "Must be unique" for a single column.');
    return;
  }
  if (!state.keys.some((key) => key.join("\u0000") === chosen.join("\u0000"))) state.keys.push(chosen);
  renderRules();
  invalidateResults("Rules changed.");
});
$("keys").addEventListener("click", (event) => {
  if (event.target.dataset.key === undefined) return;
  state.keys.splice(Number(event.target.dataset.key), 1);
  renderRules();
  invalidateResults("Rules changed.");
});
/* Every column back to text, and every rule and output setting back to its default. */
function resetRules() {
  state.columns = new Map();
  state.keys = [];
  state.profileName = null;
  $("max-field").value = "";
  $("profile-file").value = "";
  for (const id of ["out-number", "out-delimiter", "out-encoding"]) $(id).value = "";
  setDate("out-date", "");
  $("src-number").value = "canonical";
  setDate("src-date", "YYYY-MM-DD");
  $("dedupe").value = "off";
  $("dup-rows").value = "warn";
  $("line-ending").value = "crlf";
  syncColumns();
}

$("reset-rules").addEventListener("click", () => {
  resetRules();
  $("profile-note").textContent = "All rules were reset: every column is text again.";
  renderRules();
  invalidateResults("Rules reset.");
});
$("profile-file").addEventListener("change", loadProfile);
$("run-check").addEventListener("click", runCheck);
$("run-clean").addEventListener("click", runClean);
$("save-csv").addEventListener("click", () => download("csv", "Cleaned CSV"));
$("save-output-profile").addEventListener("click", () => download("output-profile", "Profile of the cleaned file"));
$("save-report").addEventListener("click", () => saveReport(false));
$("save-report-json").addEventListener("click", () => saveReport(true));
$("save-profile").addEventListener("click", saveProfile);
$("cancel").addEventListener("click", () => {
  state.queued = false;
  if (state.pending) state.pending.abort();
});
async function quitNow() {
  if (state.pending) state.pending.abort();
  try {
    await postJson("/api/quit", {});
  } catch (error) {
    /* already stopped */
  }
  state.stopped = true;
  for (const control of document.querySelectorAll("main input, main select, main button, aside button, #quit, #new-check")) control.disabled = true;
  setStatus("idle", "Datakrit has stopped. Temporary copies were removed.", "close this tab. To use it again, start Datakrit from its icon or with datakrit ui.");
}

/* Quit asks first, in a dialog on the page (no browser pop-up). */
$("quit").addEventListener("click", () => {
  if (state.stopped) return;
  $("quit-dialog").showModal();
});
$("quit-cancel").addEventListener("click", () => $("quit-dialog").close());
$("quit-confirm").addEventListener("click", () => {
  $("quit-dialog").close();
  quitNow();
});

/* ------------------------------------------------------------------ look and feel */

const THEMES = { cosmos: "Dark Modern", light: "Light+" };

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const other = theme === "cosmos" ? "light" : "cosmos";
  $("theme-label").textContent = THEMES[theme];
  $("footer-theme").textContent = THEMES[theme];
  $("theme-toggle").setAttribute("aria-label", `Color theme: ${THEMES[theme]}. Switch to ${THEMES[other]}.`);
}

$("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "cosmos" : "light";
  applyTheme(next);
  try {
    window.localStorage.setItem("datakrit-theme", next);
  } catch (error) {
    /* the choice is not remembered, which is fine */
  }
  toast(`${THEMES[next]} theme`, "Saved for this browser.");
});

/* A short confirmation in the corner; the status strip remains the announced message. */
function toast(title, text) {
  const item = el("div", { class: "toast" }, el("strong", { text: title }), el("span", { text }));
  $("toasts").append(item);
  setTimeout(() => item.remove(), 4500);
}

/* Files can also be dropped on the file area. The browser's own file list is reused, so the
   dropped files go through exactly the same steps as chosen ones. */
const dropzone = $("dropzone");
for (const type of ["dragenter", "dragover"]) {
  dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    dropzone.classList.add("over");
  });
}
for (const type of ["dragleave", "drop"]) dropzone.addEventListener(type, () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  if (state.pending || state.stopped || !event.dataTransfer.files.length) return;
  $("file").files = event.dataTransfer.files;
  chooseFile();
});
/* A file dropped anywhere else must not make the browser open it instead of the page. */
for (const type of ["dragover", "drop"]) window.addEventListener(type, (event) => event.preventDefault());

/* The step whose content shows the latest result: the preview after reading a file, the
   check after checking, the changes after a cleaning preview. */
function currentStep() {
  if (!state.file || !state.preview) return 1;
  if (!state.header.length) return 2; /* read, but not usable: step 2 says why */
  if (state.clean || (state.batch && state.batch.action === "clean")) return 5;
  if (state.check || (state.batch && state.batch.action === "check")) return 4;
  return 2;
}

/* The step navigation marks one step, and only that step's content is shown: the step last
   clicked, until the work moves on to a new step (a file read with new settings, a check,
   a cleaning preview), which then becomes the marked one. Results that are cleared because
   rules changed do not move the mark back. */
const stepMark = { progress: 0, shown: 1, read: null };

const LAST_STEP = 6;

function markStep(step) {
  stepMark.shown = step;
  for (const link of document.querySelectorAll(".steps a")) {
    if (Number(link.dataset.step) === step) link.setAttribute("aria-current", "step");
    else link.removeAttribute("aria-current");
  }
  for (let n = 1; n <= LAST_STEP; n += 1) $(`step-${n}`).hidden = n !== step;
  /* aria-disabled rather than disabled, so a button keeps its focus at the first or last step. */
  $("step-back").setAttribute("aria-disabled", String(step <= 1));
  $("step-forward").setAttribute("aria-disabled", String(step >= LAST_STEP));
  applyFind(); /* the count names the rows of the step that is shown */
}

/* The step content sits right under the navigation, so a click shows it without jumping.
   The step names in "How to use" (side panel) behave the same way. */
for (const link of document.querySelectorAll(".steps a, .howto-steps a")) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    markStep(Number(link.dataset.step));
    $(`step-${link.dataset.step}`).scrollIntoView({ block: "nearest" });
  });
}

/* ------------------------------------------------------------------ side bar */

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const narrow = window.matchMedia("(max-width: 45rem)"); /* below 720 px: overlay */
const nav = { opener: null };

function showSection(target) {
  target.scrollIntoView({ behavior: reducedMotion.matches ? "auto" : "smooth", block: "start" });
}

/* Step back / forward move the step marker and show that step. */
function moveStep(delta) {
  const step = Math.min(LAST_STEP, Math.max(1, stepMark.shown + delta));
  if (step === stepMark.shown) return;
  markStep(step);
  showSection($(`step-${step}`));
}
$("step-back").addEventListener("click", () => moveStep(-1));
$("step-forward").addEventListener("click", () => moveStep(1));

const navOpen = () => document.querySelector(".app").classList.contains("nav-open");
const navCollapsed = () => document.documentElement.dataset.nav === "collapsed";

function syncNavButtons() {
  const shown = narrow.matches ? navOpen() : !navCollapsed();
  $("nav-toggle").setAttribute("aria-expanded", String(shown));
  $("nav-open").setAttribute("aria-expanded", String(narrow.matches && navOpen()));
  $("nav-toggle").title = shown ? "Hide the side bar" : "Show the side bar";
}

/* The overlay is modal: the rest of the page cannot be reached while it is open. */
function setOverlay(open) {
  document.querySelector(".app").classList.toggle("nav-open", open);
  $("nav-scrim").hidden = !open;
  document.querySelector(".content").inert = open;
  syncNavButtons();
}

function openNav(opener) {
  nav.opener = opener;
  setOverlay(true);
  $("nav-toggle").focus();
}

function closeNav() {
  if (!navOpen()) return;
  setOverlay(false);
  const opener = nav.opener || $("nav-open");
  nav.opener = null;
  if (narrow.matches) opener.focus();
}

$("nav-open").addEventListener("click", () => openNav($("nav-open")));
$("nav-scrim").addEventListener("click", closeNav);
function setCollapsed(collapsed) {
  document.documentElement.dataset.nav = collapsed ? "collapsed" : "expanded";
  try {
    window.localStorage.setItem("datakrit-nav", collapsed ? "collapsed" : "expanded");
  } catch (error) {
    /* the state is not remembered, which is fine */
  }
  syncNavButtons();
}

$("nav-toggle").addEventListener("click", () => {
  if (narrow.matches) {
    closeNav();
    return;
  }
  setCollapsed(!navCollapsed());
});

/* While the overlay is open, Tab stays inside it and Escape closes it. */
$("sidebar").addEventListener("keydown", (event) => {
  if (!narrow.matches || !navOpen()) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeNav();
    return;
  }
  if (event.key !== "Tab") return;
  const items = [...$("sidebar").querySelectorAll("a[href], button:not(:disabled)")];
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

narrow.addEventListener("change", () => {
  if (!narrow.matches && navOpen()) {
    nav.opener = null;
    setOverlay(false);
  }
  syncNavButtons();
});

/* Rows of the side bar lead to where each feature lives on the page. */
for (const row of document.querySelectorAll(".nav-list a[data-step]")) {
  row.addEventListener("click", (event) => {
    markStep(Number(row.dataset.step));
    if (row.id === "nav-settings" && !$("rules").hidden) {
      event.preventDefault();
      $("more").open = true;
      showSection($("more"));
    }
    if (narrow.matches) {
      nav.opener = null; /* focus follows the link, not back to the toggle */
      setOverlay(false);
    }
  });
}

/* ------------------------------------------------------------------ side bar: new check */

const PROFILE_NOTE = [...$("profile-note").childNodes].map((node) => node.cloneNode(true));

const hasWork = () =>
  Boolean(state.file || state.files.length || state.check || state.clean || state.batch || state.profileName || state.columns.size);

/* Back to the start: no files, default reading settings, no rules, no results. The server's
   temporary copies are removed too (a file chosen meanwhile would replace them anyway). */
function startNewCheck() {
  const ids = [...new Set([...state.files, state.file].filter(Boolean).map((file) => file.id))];
  if (state.pending) {
    state.restart = true;
    state.queued = false;
    state.pending.abort();
  }
  state.mode = "single";
  for (const radio of document.querySelectorAll('input[name="mode"]')) radio.checked = radio.value === "single";
  for (const radio of document.querySelectorAll('input[name="delimiter"]')) radio.checked = radio.value === ",";
  $("encoding-other").value = "";
  setEncoding("utf-8");
  state.file = null;
  state.files = [];
  state.preview = null;
  state.header = [];
  state.rows = new Map();
  state.check = state.clean = state.batch = state.detail = null;
  state.cleared = false;
  resetRules();
  $("file").value = "";
  $("file").multiple = false;
  $("file-label").textContent = "CSV file";
  $("file-note").textContent = "Your file is only read. It is never changed.";
  $("profile-note").replaceChildren(...PROFILE_NOTE.map((node) => node.cloneNode(true)));
  $("more").open = false;
  setFind("");
  renderBatchFiles();
  renderPreview();
  renderRules();
  renderCheck();
  renderClean();
  stepMark.progress = 0;
  stepMark.read = null;
  refreshButtons();
  markStep(1);
  setStatus("idle", "New check: nothing is loaded.", "choose a CSV file in the box at the top.");
  for (const id of ids) postJson("/api/file/remove", { file_id: id }).catch(() => {});
  if (narrow.matches) {
    nav.opener = null;
    setOverlay(false);
  }
  $("file").focus();
}

/* Nothing to lose: start at once. Otherwise ask first, in a dialog on the page. */
$("new-check").addEventListener("click", () => {
  if (state.stopped) return;
  if (hasWork()) $("new-dialog").showModal();
  else startNewCheck();
});
$("new-cancel").addEventListener("click", () => $("new-dialog").close());
$("new-confirm").addEventListener("click", () => {
  $("new-dialog").close();
  startNewCheck();
});

/* ------------------------------------------------------------------ side bar: find */

/* The text of a table row to search: a rule row by its column name only (its lists hold the
   names of every type), other rows without their buttons. */
function rowText(row) {
  if (row.dataset.column !== undefined) return row.dataset.column;
  return [...row.cells]
    .filter((cell) => !cell.querySelector("button"))
    .map((cell) => cell.textContent)
    .join(" ");
}

/* Find hides the table rows of the step area that do not contain the text. It runs again
   whenever a table is drawn, so new results are filtered too. */
function applyFind() {
  const typed = $("find").value.trim();
  const query = typed.toLowerCase();
  const current = $(`step-${stepMark.shown}`);
  let shown = 0;
  let total = 0;
  for (const row of document.querySelectorAll(".step-area tbody tr")) {
    const match = !query || rowText(row).toLowerCase().includes(query);
    row.hidden = !match;
    if (current.contains(row)) {
      total += 1;
      if (match) shown += 1;
    }
  }
  $("find-note").hidden = !query;
  if (query) $("find-note-text").replaceChildren("Showing only the rows that contain ", el("b", { text: `“${typed}”` }), ".");
  let said = "Shows only the table rows that contain this text.";
  if (query) said = total ? `${shown} of ${count(total, "row")} in this step match.` : "This step has no table rows yet.";
  if ($("find-count").textContent !== said) $("find-count").textContent = said;
}

function setFind(value) {
  $("find").value = value;
  applyFind();
}

function showFind(open) {
  if (open && !narrow.matches && navCollapsed()) setCollapsed(false);
  $("find-box").hidden = !open;
  $("find-toggle").setAttribute("aria-expanded", String(open));
  if (open) $("find").focus();
  else setFind("");
}

$("find-toggle").addEventListener("click", () => showFind($("find-box").hidden));
$("find").addEventListener("input", applyFind);
$("find").addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  /* Escape first empties the field, then closes it; the overlay stays open. */
  event.preventDefault();
  event.stopPropagation();
  if ($("find").value) setFind("");
  else {
    showFind(false);
    $("find-toggle").focus();
  }
});
$("find-clear").addEventListener("click", () => {
  setFind("");
  if (!$("find-box").hidden && !(narrow.matches && !navOpen())) $("find").focus();
  else $("main").focus();
});
new MutationObserver(applyFind).observe(document.querySelector(".step-area"), { childList: true, subtree: true });

/* ------------------------------------------------------------------ side bar: in this session */

/* The SVG namespace, taken from an icon of the page (the script names no addresses). */
const SVG = $("nav-toggle").querySelector("svg").namespaceURI;
const circle = ["circle", { cx: "12", cy: "12", r: "10" }];
/* Inline SVG status icons: a circle with a check, with an exclamation mark, and dashed. */
const STATE_ICONS = {
  ok: [circle, ["path", { d: "m9 12 2 2 4-4" }]],
  bad: [circle, ["line", { x1: "12", x2: "12", y1: "8", y2: "12" }], ["line", { x1: "12", x2: "12.01", y1: "16", y2: "16" }]],
  none: [
    "M10.1 2.182a10 10 0 0 1 3.8 0",
    "M13.9 21.818a10 10 0 0 1-3.8 0",
    "M17.609 3.721a10 10 0 0 1 2.69 2.7",
    "M2.182 13.9a10 10 0 0 1 0-3.8",
    "M20.279 17.609a10 10 0 0 1-2.7 2.69",
    "M21.818 10.1a10 10 0 0 1 0 3.8",
    "M3.721 6.391a10 10 0 0 1 2.7-2.69",
    "M6.391 20.279a10 10 0 0 1-2.69-2.7",
  ].map((d) => ["path", { d }]),
};

/* A single-choice list with the chevron of "How to use", like the lists in index.html; app.css
   turns it while the list is open. */
function withChevron(select) {
  return el("span", { class: "select-wrap" }, select, icon([["path", { d: "m6 9 6 6 6-6" }]], "select-chevron"));
}

function icon(shapes, extra) {
  const make = (tag, attrs) => {
    const node = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const base = { class: `icon ${extra}`, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "aria-hidden": "true" };
  const svg = make("svg", { ...base, "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" });
  svg.append(...shapes.map(([tag, attrs]) => make(tag, attrs)));
  return svg;
}

const batchEntry = (file) => {
  if (state.mode !== "batch" || !state.batch) return null;
  const index = state.batch.files.findIndex((f) => f.file_id === file.id);
  return index >= 0 ? state.batch.report.files[index] : null;
};

/* Not checked, problems, or fine: from the latest result that covers the file. */
function fileState(file) {
  const entry = batchEntry(file);
  if (entry) {
    if (entry.status === "failed" || entry.status === "incomplete") return ["bad", "not fully read"];
    if (entry.status === "invalid" || entry.status === "blocked") return ["bad", "problems found"];
    if (entry.structure_only) return ["none", "values not checked"];
    return ["ok", entry.status === "ready" ? "ready to save" : "no problems"];
  }
  if (!state.file || state.file.id !== file.id) return ["none", "not checked"];
  if (state.clean) {
    const status = state.clean.data.report.summary.status;
    if (status === "ready") return ["ok", "ready to save"];
    return ["bad", status === "incomplete" ? "not fully read" : "problems found"];
  }
  if (state.check) {
    const verdict = state.check.report.verdict.state;
    if (verdict === "passed") return ["ok", "no problems"];
    if (verdict === "passed_structure_only") return ["none", "values not checked"];
    return ["bad", verdict === "incomplete" ? "not fully read" : "problems found"];
  }
  if (state.preview) {
    if (!state.preview.report.scan.complete) return ["bad", "not fully read"];
    if (state.preview.report.summary.errors) return ["bad", "structure problems"];
  }
  return ["none", "not checked"];
}

function renderSession() {
  const list = $("session-files");
  const focused = document.activeElement && document.activeElement.dataset.sessionFile;
  const files = loadedFiles();
  /* The open file: the one whose details are shown, otherwise the one in the preview. */
  const open = state.detail ? state.detail.fileId : state.file && state.file.id;
  list.replaceChildren(
    ...files.map((file) => {
      const [kind, text] = fileState(file);
      const entry = batchEntry(file);
      const rows = entry ? entry.data_records : state.rows.get(file.id);
      const meta = `${rows === undefined ? "not read yet" : count(rows, "row")} · ${text}`;
      const current = open === file.id;
      return el(
        "li",
        null,
        el(
          "button",
          { type: "button", class: "session-row", "data-session-file": String(file.id), "aria-current": current ? "true" : null },
          icon(STATE_ICONS[kind], `state-${kind}`),
          el("span", { class: "session-name", text: file.name }),
          el("span", { class: "session-meta", text: meta })
        )
      );
    })
  );
  if (!files.length) list.append(el("li", { class: "nav-hint session-empty", text: "No files yet." }));
  if (focused) {
    const again = list.querySelector(`[data-session-file="${focused}"]`);
    if (again) again.focus();
  }
}

/* Opens a file at its latest result. In several-files mode with a result, that is the file's
   details (reading it again would drop the result of every file). */
function openFile(id) {
  if (state.mode === "batch" && state.batch && state.batch.files.some((f) => f.file_id === id)) {
    const step = state.batch.action === "check" ? 4 : 5;
    markStep(step);
    showSection($(`step-${step}`));
    if (!state.detail || state.detail.fileId !== id) showBatchDetail(id);
    return;
  }
  if (state.mode === "batch" && (!state.file || state.file.id !== id)) {
    previewBatchFile(id);
    return;
  }
  const step = currentStep();
  markStep(step);
  showSection($(`step-${step}`));
}

$("session-files").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-session-file]");
  if (!button || state.pending || state.stopped) return;
  if (narrow.matches) {
    nav.opener = null;
    setOverlay(false);
    $("main").focus({ preventScroll: true });
  }
  openFile(Number(button.dataset.sessionFile));
});

/* ------------------------------------------------------------------ side panel rows */

const DELIMITER_NAMES = { ",": "Comma", ";": "Semicolon", "\t": "Tab" };
const ENCODING_NAMES = { "utf-8": "UTF-8", cp1252: "Windows-1252", "latin-1": "Latin-1", "utf-16": "UTF-16" };

/* A column "has rules" when it is checked or repaired in any way. */
const ruled = (rule) => rule.type !== "text" || rule.required || rule.unique || rule.trim || rule.normalize || rule.neutralize;

function renderPanel() {
  const loaded = Boolean(state.file) && state.header.length > 0;
  $("panel-profile").textContent = state.profileName || "No profile";
  $("panel-profile-save").disabled = state.stopped || !loaded;

  const rules = [...state.columns.values()];
  const total = state.columns.size;
  const withRules = rules.filter(ruled).length;
  $("panel-columns").textContent = total
    ? `${withRules.toLocaleString("en-US")} of ${count(total, "column")} ${total === 1 ? "has" : "have"} rules`
    : "No file yet";

  const keys = [...[...state.columns].filter(([, rule]) => rule.unique).map(([name]) => [name]), ...state.keys];
  $("panel-keys").textContent = keys.length ? keys.map((key) => key.join(" + ")).join("; ") : "None";

  const delimiter = $("out-delimiter").value || currentDelimiter();
  const encoding = $("out-encoding").value.trim() || currentEncoding() || "utf-8";
  const protectedColumns = rules.filter((rule) => rule.neutralize && rule.type === "text").length;
  const formulas = protectedColumns ? `formulas protected in ${count(protectedColumns, "column")}` : "formulas not protected";
  $("panel-output").textContent =
    `${DELIMITER_NAMES[delimiter] || delimiter}, ${ENCODING_NAMES[encoding.toLowerCase()] || encoding}, ` +
    `${$("line-ending").value.toUpperCase()}; ${formulas}`;
}

/* The actions lead to the controls in step 3; the controls stay the only place to change. */
function showRules(focusId, more) {
  markStep(3);
  const ready = !$("rules").hidden;
  if (ready && more) $("more").open = true;
  showSection(ready && more ? $("more") : $("step-3"));
  const target = ready && (focusId ? $(focusId) : $("columns-body").querySelector("tr:not([hidden]) select"));
  if (target) target.focus({ preventScroll: true });
}

$("panel-profile-load").addEventListener("click", () => {
  if (state.pending || state.stopped) return;
  markStep(3);
  $("profile-file").click();
});
$("panel-profile-save").addEventListener("click", () => {
  if (state.file && state.header.length) saveProfile();
});
$("panel-columns-edit").addEventListener("click", () => showRules(null, false));
$("panel-keys-add").addEventListener("click", () => showRules("key-columns", true));
$("panel-output-edit").addEventListener("click", () => showRules("out-delimiter", true));
$("panel-theme").addEventListener("click", () => $("theme-toggle").click());

/* Migration: Datakrit was called CSV Tidy until 1.2.0, which kept the theme, side-bar, and
   "How to use" choices under csv-tidy-* keys. theme.js moves them before the first paint;
   this repeats it in case that script could not, before the choices are read here. */
function migrateStoredChoices() {
  try {
    const store = window.localStorage;
    for (const name of ["theme", "nav", "howto"]) {
      const old = store.getItem("csv-tidy-" + name);
      if (old !== null && store.getItem("datakrit-" + name) === null) {
        store.setItem("datakrit-" + name, old);
        store.removeItem("csv-tidy-" + name);
      }
    }
  } catch (error) {
    /* storage is blocked: nothing to move */
  }
}
migrateStoredChoices();

/* "How to use" is a native <details>: it opens and closes by itself; only the choice is kept. */
try {
  $("howto").open = window.localStorage.getItem("datakrit-howto") === "open";
} catch (error) {
  /* storage is blocked: the guide starts closed */
}
$("howto").addEventListener("toggle", () => {
  try {
    window.localStorage.setItem("datakrit-howto", $("howto").open ? "open" : "closed");
  } catch (error) {
    /* the choice is not remembered, which is fine */
  }
});

function refreshLook() {
  const step = currentStep();
  /* The file and the settings it was read with: reading again with others shows step 2. */
  const read = state.preview && state.file ? `${state.file.id}|${currentDelimiter()}|${currentEncoding()}` : null;
  const reread = step === 2 && read !== stepMark.read;
  /* Without a file (new mode, last file removed) everything starts again at step 1. */
  const restart = step === 1 && stepMark.progress > 1;
  if (step > stepMark.progress || reread || restart) markStep(step);
  else markStep(stepMark.shown);
  stepMark.progress = step;
  /* Remembered only once the preview is the latest result: while a new file is being read,
     earlier results can still be present for a moment. */
  if (step === 2) stepMark.read = read;
  const batchMode = state.mode === "batch";
  let name = "No file chosen";
  if (batchMode && state.files.length) name = count(state.files.length, "file") + " chosen";
  else if (!batchMode && state.file) name = state.file.name;
  $("file-name").textContent = name;
  $("dz-hint").textContent = batchMode
    ? "Click + to browse, or drop .csv files here (several at once)"
    : "Click + to browse, or drop a .csv file here";
  renderCrumbs();
  renderSession();
  renderPanel();
}

/* ------------------------------------------------------------------ breadcrumb and file menu */

function loadedFiles() {
  if (state.mode === "batch") return state.files;
  return state.file ? [state.file] : [];
}

function renderCrumbs() {
  const files = loadedFiles();
  $("crumb-none").hidden = files.length > 0;
  $("crumb-current").hidden = files.length === 0;
  $("crumb-name").textContent = state.file ? state.file.name : "";
  $("crumb-file").disabled = Boolean(state.pending) || state.stopped;
  $("crumb-file").setAttribute("aria-label", state.file ? `${state.file.name}: choose the file to show` : "Choose the file to show");
  let title = "Check and clean a CSV file";
  if (state.mode === "batch" && files.length > 1) title = `${count(files.length, "file")} with the same rules`;
  else if (state.file) title = state.file.name;
  $("page-title").textContent = title;
  if (!files.length) closeFileMenu(false);
}

function openFileMenu() {
  const items = loadedFiles().map((file) =>
    el(
      "li",
      null,
      el("button", { type: "button", "data-menu-file": String(file.id), "aria-current": state.file && state.file.id === file.id ? "true" : null }, file.name)
    )
  );
  items.push(
    el("li", { class: "menu-sep" }, el("button", { type: "button", "data-menu-choose": "1" }, state.mode === "batch" ? "Add files…" : "Choose another file…"))
  );
  $("file-menu").replaceChildren(...items);
  $("file-menu").hidden = false;
  $("crumb-file").setAttribute("aria-expanded", "true");
  $("file-menu").querySelector("button").focus();
}

function closeFileMenu(returnFocus) {
  if ($("file-menu").hidden) return;
  $("file-menu").hidden = true;
  $("crumb-file").setAttribute("aria-expanded", "false");
  if (returnFocus) $("crumb-file").focus();
}

$("crumb-file").addEventListener("click", () => {
  if ($("file-menu").hidden) openFileMenu();
  else closeFileMenu(true);
});
$("file-menu").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  closeFileMenu(true);
  if (button.dataset.menuChoose) {
    $("file").click();
  } else {
    openFile(Number(button.dataset.menuFile));
  }
});
$("file-menu").addEventListener("keydown", (event) => {
  const buttons = [...$("file-menu").querySelectorAll("button")];
  const at = buttons.indexOf(document.activeElement);
  if (event.key === "Escape") {
    event.preventDefault();
    closeFileMenu(true);
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const next = (at + (event.key === "ArrowDown" ? 1 : buttons.length - 1)) % buttons.length;
    buttons[next].focus();
  }
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".crumb-menu")) closeFileMenu(false);
});
$("crumb-files").addEventListener("click", () => markStep(1));

/* ------------------------------------------------------------------ primary action */

/* One button in the input card does the next thing: check, then preview the cleaning, then
   show the ways to save. */
function refreshPrimary(busy, loaded) {
  const button = $("primary-action");
  let next = "check";
  if (state.clean || (state.batch && state.batch.action === "clean")) next = "save";
  else if (state.check || (state.batch && state.batch.action === "check")) next = "clean";
  button.dataset.next = next;
  button.textContent = { check: "Check", clean: "Preview cleaning", save: "Save" }[next];
  /* While something runs the button stays pressable (aria-disabled): a press waits for it. */
  button.disabled = state.stopped || !loaded;
  button.setAttribute("aria-disabled", String(busy));
}

function primaryAction() {
  if (state.pending) {
    state.queued = true;
    return;
  }
  if (!state.file || !state.header.length) return;
  const next = $("primary-action").dataset.next;
  if (next === "check") runCheck();
  else if (next === "clean") runClean();
  else {
    markStep(6);
    showSection($("step-6"));
    const first = $("step-6").querySelector("button:not(:disabled)");
    if (first) first.focus({ preventScroll: true });
  }
}

$("primary-action").addEventListener("click", primaryAction);

applyTheme(document.documentElement.dataset.theme === "light" ? "light" : "cosmos");
syncNavButtons();
markStep(stepMark.shown);
fillDatePicks();
renderRules();
refreshButtons();

/* While the page is open it checks in, so a server started without a console (the Datakrit
   icon) knows it is still in use. Once the page is closed, the server stops by itself. */
setInterval(async () => {
  if (state.stopped || state.pending) return;
  try {
    await postJson("/api/ping", {});
  } catch (error) {
    state.stopped = true;
    for (const control of document.querySelectorAll("main input, main select, main button, aside button, #quit, #new-check")) control.disabled = true;
    setStatus("bad", "Datakrit is not running any more.", "start it again from the Datakrit icon. Your files were not changed.");
  }
}, PING_SECONDS * 1000);
