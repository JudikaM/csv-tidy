"use strict";
/* CSV Tidy local interface. All file contents are placed in the page with textContent, never
   as HTML. Every result comes from the local csv-tidy process; this script validates nothing. */

const $ = (id) => document.getElementById(id);
const meta = (name) => document.querySelector(`meta[name="${name}"]`).content;
const TOKEN = meta("csv-tidy-token");
const MAX_FILE_MB = Number(meta("csv-tidy-max-file-mb")) || 200;
const KNOWN_ENCODINGS = ["utf-8", "cp1252", "latin-1", "utf-16"];
const NUMBER_LABELS = { canonical: "1250.50", id: "1.250,50", us: "1,250.50" };

const state = {
  file: null, // {id, name, size}
  header: [],
  preview: null,
  columns: new Map(), // name -> rule
  keys: [], // combined keys (two or more columns)
  maxFieldChars: null,
  profileName: null,
  check: null, // {id, report, profile}
  clean: null, // {id, data, profile}
  pending: null, // AbortController of the running request
  cleared: false, // results were dropped since the last run
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
  refreshButtons();
}

async function request(path, options) {
  const response = await fetch(path, {
    method: "POST",
    ...options,
    headers: { "X-CSV-Tidy-Token": TOKEN, ...(options.headers || {}) },
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
  try {
    await action(state.pending.signal);
  } catch (error) {
    if (error.name === "AbortError") {
      setStatus("warn", "Cancelled. Nothing was changed or saved.", "run the step again when you are ready.");
    } else if (error instanceof TypeError) {
      setStatus("bad", "CSV Tidy is not answering.", "make sure the csv-tidy ui window is still open, then try again.");
    } else {
      setStatus("bad", error.message, "correct this, then try again.");
    }
  } finally {
    state.pending = null;
    setBusy(false);
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

function buildProfile() {
  const source = {
    delimiter: currentDelimiter(),
    encoding: currentEncoding(),
    number_format: $("src-number").value,
    date_format: $("src-date").value.trim(),
  };
  if (state.maxFieldChars) source.max_field_chars = state.maxFieldChars;
  const output = { line_ending: $("line-ending").value };
  if ($("out-number").value) output.number_format = $("out-number").value;
  if ($("out-date").value.trim()) output.date_format = $("out-date").value.trim();
  if ($("out-delimiter").value) output.delimiter = $("out-delimiter").value;
  if ($("out-encoding").value.trim()) output.encoding = $("out-encoding").value.trim();
  const columns = {};
  const keys = [];
  const trim = [];
  const normalize = [];
  for (const [name, rule] of state.columns) {
    const spec = { type: rule.type, required: rule.required };
    if (rule.type === "decimal" && rule.numberFormat) spec.number_format = rule.numberFormat;
    if (rule.type === "date" && rule.dateFormat) spec.date_format = rule.dateFormat;
    columns[name] = spec;
    if (rule.unique) keys.push([name]);
    if (rule.trim) trim.push(name);
    if (rule.normalize && rule.type !== "text") normalize.push(name);
  }
  return {
    schema_version: 1,
    source,
    output,
    columns,
    duplicates: { rows: $("dup-rows").value, keys: [...keys, ...state.keys] },
    transform: { trim, normalize, deduplicate: $("dedupe").value },
  };
}

function applyProfile(profile, name) {
  const source = profile.source || {};
  const output = profile.output || {};
  let reread = false;
  if (source.delimiter && source.delimiter !== currentDelimiter()) {
    document.querySelector(`input[name="delimiter"][value="${source.delimiter === ";" ? ";" : ","}"]`).checked = true;
    reread = true;
  }
  if (source.encoding && source.encoding !== currentEncoding()) {
    setEncoding(source.encoding);
    reread = true;
  }
  $("src-number").value = source.number_format || "canonical";
  $("src-date").value = source.date_format || "YYYY-MM-DD";
  state.maxFieldChars = source.max_field_chars || null;
  $("out-number").value = output.number_format || "";
  $("out-date").value = output.date_format || "";
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
  const fileDate = $("src-date").value.trim() || "YYYY-MM-DD";
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
    } else if (rule.type === "date") {
      format = el("input", {
        type: "text",
        id: id("dateFormat"),
        list: "date-formats",
        "aria-label": `How dates are written in column ${name}`,
        "data-field": "dateFormat",
        placeholder: `Like the file (${fileDate})`,
        autocomplete: "off",
        spellcheck: "false",
      });
      format.value = rule.dateFormat;
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
      el("td", null, type),
      el("td", null, format),
      tick("required", "Must not be empty"),
      tick("unique", "Must be unique"),
      tick("trim", "Trim spaces"),
      tick("normalize", "Convert format", !typed)
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
  if (state.check || state.clean) state.cleared = true;
  state.check = null;
  state.clean = null;
  renderCheck();
  renderClean();
  refreshButtons();
  if (message && state.file) {
    setStatus(
      "warn",
      state.cleared ? `${message} Earlier results were cleared because they no longer match.` : message,
      state.header.length ? "select Check file (step 4)." : "choose a file that can be read (steps 1 and 2)."
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
      el("td", null, tag ? "Nothing; already handled." : issue.suggestion)
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
  box.hidden = !state.check;
  box.replaceChildren();
  if (!state.check) return;
  const report = state.check.report;
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
  box.hidden = !state.clean;
  box.replaceChildren();
  if (!state.clean) return;
  const data = state.clean.data;
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
                el("td", null, c.steps.map((s) => ({ trim: "trim spaces", normalize: "convert format" })[s] || s).join(", "))
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

function refreshButtons() {
  const busy = Boolean(state.pending) || state.stopped;
  const loaded = Boolean(state.file) && state.header.length > 0;
  $("run-check").disabled = busy || !loaded;
  $("run-clean").disabled = busy || !loaded;
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
  const response = await postJson("/api/preview", { file_id: state.file.id, delimiter: currentDelimiter(), encoding: currentEncoding() }, signal);
  state.preview = await response.json();
  state.header = state.preview.header ? [...new Set(state.preview.header)] : [];
  syncColumns();
  state.check = null;
  state.clean = null;
  renderPreview();
  renderRules();
  renderCheck();
  renderClean();
  const scan = state.preview.report.scan;
  const errors = state.preview.report.summary.errors;
  const hint = state.preview.report.issues.find((issue) => issue.code === "possible_wrong_delimiter");
  if (!scan.complete) {
    setStatus("bad", "This file could not be read to the end.", "check the separator and the encoding in step 1, or repair the file. Details are in step 2.");
  } else if (hint) {
    setStatus("warn", "The file loaded as one wide column.", "switch the separator in step 1; the file probably uses the other one.");
  } else if (errors) {
    setStatus("bad", `${lead} The file has ${count(errors, "structure problem")}.`, "see step 2, then set the rules (step 3) and select Check file.");
  } else {
    setStatus("ok", `${lead} ${count(scan.data_records, "row")}, ${count(state.header.length, "column")}.`, "confirm the preview, set the rules in step 3 (or load a profile), then select Check file.");
  }
}

function chooseFile() {
  const file = $("file").files[0];
  if (!file) return;
  if (file.size > MAX_FILE_MB * 1024 * 1024) {
    setStatus("bad", `This file is larger than ${MAX_FILE_MB} MB.`, "split the file, or start csv-tidy ui with a higher --max-file-mb.");
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

function rereadFile(message) {
  if (!state.file) return;
  run("Reading the file again…", (signal) => loadPreview(signal, message));
}

function validateRulesLocally() {
  if ($("dedupe").value === "keys" && state.keys.length === 0 && ![...state.columns.values()].some((rule) => rule.unique)) {
    throw new Error('"Also remove rows that repeat a unique value" needs at least one column ticked "Must be unique" (step 3).');
  }
  if (!currentEncoding()) throw new Error("Type the name of the encoding in step 1.");
}

function runCheck() {
  run("Checking the file…", async (signal) => {
    validateRulesLocally();
    const profile = buildProfile();
    const response = await postJson("/api/check", { file_id: state.file.id, profile, profile_name: state.profileName }, signal);
    const data = await response.json();
    state.check = { id: data.result_id, report: data.report, profile };
    renderCheck();
    const s = data.report.summary;
    const verdict = data.report.verdict.state;
    if (verdict === "incomplete") {
      setStatus("bad", "The file could not be read to the end.", "check the separator and encoding in step 1, or repair the file.");
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
  run("Preparing the cleaned copy…", async (signal) => {
    validateRulesLocally();
    const profile = buildProfile();
    const response = await postJson("/api/clean", { file_id: state.file.id, profile, profile_name: state.profileName }, signal);
    const data = await response.json();
    state.clean = { id: data.result_id, data, profile };
    renderClean();
    const report = data.report;
    if (report.summary.status === "ready") {
      setStatus(
        "ok",
        `Ready to save: ${count(report.changes.output_records, "row")}, ${count(report.changes.changed_fields, "value")} changed, ${count(report.changes.removed_records, "row")} removed.`,
        "review the changes in step 5, then select Save cleaned CSV (step 6)."
      );
    } else if (report.summary.status === "incomplete") {
      setStatus("bad", "The file could not be read to the end; nothing can be saved.", "check the separator and encoding in step 1, or repair the file.");
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
}

function download(kind, what) {
  run(`Saving ${what.toLowerCase()}…`, async (signal) => {
    const fromCheck = kind.startsWith("check-");
    const stored = fromCheck ? state.check : state.clean;
    const response = await postJson("/api/download", { result_id: stored.id, kind, profile: stored.profile }, signal);
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
    const response = await postJson("/api/profile/toml", { profile: buildProfile(), file_name: state.file.name }, signal);
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
      setStatus("ok", `Profile ${data.name} loaded.`, "review the rules in step 3, then select Check file.");
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
  rule[field] = event.target.type === "checkbox" ? event.target.checked : event.target.value.trim();
  if (rule.type === "text") rule.normalize = false;
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
for (const id of ["src-number", "src-date", "out-number", "out-date", "dedupe", "dup-rows", "out-delimiter", "out-encoding", "line-ending"]) {
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
$("reset-rules").addEventListener("click", () => {
  state.columns = new Map();
  state.keys = [];
  state.profileName = null;
  state.maxFieldChars = null;
  $("profile-file").value = "";
  $("profile-note").textContent = "All rules were reset: every column is text again.";
  for (const id of ["out-number", "out-date", "out-delimiter", "out-encoding"]) $(id).value = "";
  $("src-number").value = "canonical";
  $("src-date").value = "YYYY-MM-DD";
  $("dedupe").value = "off";
  $("dup-rows").value = "warn";
  $("line-ending").value = "crlf";
  syncColumns();
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
$("cancel").addEventListener("click", () => state.pending && state.pending.abort());
$("quit").addEventListener("click", async () => {
  if (state.pending) state.pending.abort();
  try {
    await postJson("/api/quit", {});
  } catch (error) {
    /* already stopped */
  }
  state.stopped = true;
  for (const control of document.querySelectorAll("main input, main select, main button, #quit")) control.disabled = true;
  setStatus("idle", "CSV Tidy has stopped. Temporary copies were removed.", "close this tab. To use it again, start csv-tidy ui.");
});

renderRules();
refreshButtons();
