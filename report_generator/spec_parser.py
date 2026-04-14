"""
spec_parser.py — Parse a reviewed spec .md file into a report dict.

The returned dict is compatible with rdl_generator.generate_rdl() and
pbip_generator.generate_pbip().  Any values confirmed in the spec
(connection string, model name, SQL query) are stored under underscore-
prefixed keys (e.g. ``_spec_model``) so the generators can use them in
preference to auto-inferred values.

Usage:
    from report_generator.spec_parser import parse_spec
    report = parse_spec("output/specs/mo-wild-ball-sales-report.md")
"""

import re
from pathlib import Path


# ── Section splitting ──────────────────────────────────────────────────────────

def _split_sections(text: str) -> dict:
    """Return {heading: body_text} for every ## section in *text*."""
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


# ── Metadata ───────────────────────────────────────────────────────────────────

def _parse_metadata(text: str) -> dict:
    """Parse ``- **Key:** value`` bullet lines from the Metadata section."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\s*-\s+\*\*([^*]+)\*\*[:\s]+(.+)", line)
        if not m:
            continue
        key = m.group(1).strip().rstrip(":").lower()   # strip trailing colon from **Key:**
        val = m.group(2).strip().strip("`").split("*(")[0].strip().rstrip("*").strip()
        if "legacy path" in key:
            result.setdefault("legacy_path", val)
        elif "legacy user" in key:
            result.setdefault("legacy_users", val)
        elif "description" in key:
            result.setdefault("description", val)
        elif "report format" in key:
            result.setdefault("format", val)
        elif "output folder" in key or "new folder" in key:
            result.setdefault("folder", val)
        elif key == "folder":
            result.setdefault("folder", val)
        elif "sort" in key:
            result.setdefault("sort", val)
        elif "notes" in key:
            result.setdefault("notes", val)
        elif "report title" in key:
            result.setdefault("title", val)
    return result


# ── Data Source ────────────────────────────────────────────────────────────────

def _parse_datasource(text: str) -> dict:
    """
    Detect datasource type and extract connection details.

    Handles three formats emitted by spec_generator.py:

    Semantic model (new):
        - **Name:** ``MissouriD1V1_MO_Sales``
        - **Provider:** ``PBIDATASET``
        - **Connection string:** ...code block...
        - **Semantic model:** ``MO_Sales.SemanticModel`` (dataset GUID: ``...``)

    DB2 ODBC:
        - **Type:** DB2 / ARDB (ODBC)
        - **Source Name:** ``BOADB``
        - **DSN:** ``MOS-Q1-BOADB``

    Snowflake ODBC:
        - **Type:** Snowflake (ODBC)
        - **Source Name:** ``LPC_E2_SFODBC``
        - **DSN:** ``MOS-PX-SFODBC``
    """
    result: dict[str, str] = {}

    for line in text.splitlines():
        m = re.match(r"\s*-\s+\*\*([^*]+)\*\*[:\s]+(.+)", line)
        if not m:
            continue
        key = m.group(1).strip().rstrip(":").lower()   # strip trailing colon from **Key:**
        val = m.group(2).strip().strip("`").split("*(")[0].strip()

        if key == "provider":
            if "PBIDATASET" in val.upper():
                result["type"] = "semantic_model"
            elif "ODBC" in val.upper():
                result.setdefault("type", "db2")   # refined below if Snowflake
        elif key == "type":
            val_l = val.lower()
            if "snowflake" in val_l:
                result["type"] = "snowflake"
            elif "db2" in val_l or "ardb" in val_l:
                result["type"] = "db2"
            elif "semantic" in val_l:
                result["type"] = "semantic_model"
        elif key == "name":
            result["datasource_name"] = val
        elif key in ("dsn", "dsn name"):
            result["dsn"] = val
        elif key == "source name":
            result["source_name"] = val

    # Semantic model name  →  "MO_Sales.SemanticModel"
    sm_m = re.search(r"\*\*Semantic model\*\*[:\s]+`([^.`]+)\.SemanticModel`", text)
    if sm_m:
        result["semantic_model"] = sm_m.group(1).strip()

    # Dataset GUID
    guid_m = re.search(r"dataset GUID[:\s]+`([^`]+)`", text, re.IGNORECASE)
    if guid_m:
        result["guid"] = guid_m.group(1).strip()

    # Connection string from indented code block
    cs_m = re.search(
        r"\*\*Connection string\*\*[^\n]*\n\s*```\n([\s\S]+?)\n\s*```",
        text,
    )
    if cs_m:
        cs_lines = [l.strip() for l in cs_m.group(1).splitlines() if l.strip()]
        result["connect_string"] = " ".join(cs_lines)

    result.setdefault("type", "semantic_model")
    return result


# ── Parameters / Filters ───────────────────────────────────────────────────────

def _parse_table(text: str) -> list[list[str]]:
    """
    Parse all non-separator table rows from *text*.
    Returns list of cell lists (strings already stripped).
    Skips header-separator rows (|---|---|).
    """
    rows = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]          # drop empty edge cells
        if not cells:
            continue
        if all(re.match(r"^[-:\s]+$", c) for c in cells):
            continue                              # separator row
        rows.append(cells)
    return rows


def _parse_parameters(text: str) -> list:
    """
    Parse a Parameters table:
        | Label | Single / Multiple | Default / Notes |

    Also handles the extended ODBC template format:
        | # | Label | DataType | Single / Multiple | Required | Default / Notes |
    """
    rows = _parse_table(text)
    if not rows:
        return []

    header = [c.lower() for c in rows[0]]
    data_rows = rows[1:]

    # Locate relevant column indices
    label_idx  = next((i for i, h in enumerate(header) if "label" in h), 0)
    select_idx = next(
        (i for i, h in enumerate(header) if "single" in h or "multiple" in h),
        min(1, len(header) - 1),
    )
    notes_idx  = len(header) - 1

    params = []
    for cells in data_rows:
        if label_idx >= len(cells):
            continue
        label = cells[label_idx].replace("\\|", "|").strip()
        required = label.endswith("*")
        label = label.rstrip("*").strip()

        # Skip header-like rows and the always-present hidden ExecDateTime param
        if not label or label.lower() in ("label", "parameter label", "executions"):
            continue
        if label == "ExecDateTime":
            continue

        select_raw = cells[select_idx].strip() if select_idx < len(cells) else "Single"
        select = "Multiple" if "multiple" in select_raw.lower() else "Single"
        notes  = cells[notes_idx].strip() if notes_idx < len(cells) else ""

        params.append({
            "label":    label,
            "required": required,
            "select":   select,
            "notes":    notes,
        })
    return params


def _parse_filters(text: str) -> list:
    """
    Parse a Filters table:
        | Label | Filter Type | Context | Single / Multiple | Default / Notes |
    """
    rows = _parse_table(text)
    if not rows:
        return []

    header = [c.lower() for c in rows[0]]
    data_rows = rows[1:]

    label_idx   = next((i for i, h in enumerate(header) if "label" in h), 0)
    type_idx    = next((i for i, h in enumerate(header) if "filter type" in h or "type" in h), 1)
    ctx_idx     = next((i for i, h in enumerate(header) if "context" in h), 2)
    select_idx  = next(
        (i for i, h in enumerate(header) if "single" in h or "multiple" in h),
        3,
    )
    notes_idx   = len(header) - 1

    def _get(cells, idx):
        return cells[idx].strip() if idx < len(cells) else ""

    filters = []
    for cells in data_rows:
        if label_idx >= len(cells):
            continue
        label = _get(cells, label_idx).replace("\\|", "|")
        required = label.endswith("*")
        label = label.rstrip("*").strip()
        if not label or label.lower() in ("label", "filter label"):
            continue

        select_raw = _get(cells, select_idx)
        filters.append({
            "label":       label,
            "required":    required,
            "filter_type": _get(cells, type_idx) or "Global",
            "context":     _get(cells, ctx_idx),
            "select":      "Multiple" if "multiple" in select_raw.lower() else "Single",
            "notes":       _get(cells, notes_idx),
        })
    return filters


# ── Datasets / SQL ─────────────────────────────────────────────────────────────

def _parse_sql(text: str) -> str | None:
    """Extract the first SQL query from a ```sql...``` or plain ```...``` block."""
    # Labelled SQL block
    m = re.search(r"```sql\n([\s\S]+?)\n```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Plain code block that starts with SELECT / WITH
    m = re.search(r"```\n((?:SELECT|WITH)[\s\S]+?)\n```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


# ── Layout ─────────────────────────────────────────────────────────────────────

def _parse_layout(text: str) -> dict:
    """
    Parse the Layout section into the same dict schema as frd_parser:
        {section_name: {"columns": [...], "raw": ""}}

    Handles optional ### sub-headings for multi-tab reports.
    """
    layout: dict[str, dict] = {}
    current_section = "main"
    header_seen = False

    for line in text.splitlines():
        # Sub-section heading (### Tab 1: Sales Data)
        if line.startswith("### "):
            current_section = line[4:].strip()
            header_seen = False
            layout.setdefault(current_section, {"columns": [], "raw": ""})
            continue

        if "|" not in line:
            continue

        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not cells:
            continue

        # Separator
        if all(re.match(r"^[-:\s]+$", c) for c in cells):
            continue

        # Header row — must contain "Column Header"
        if "column header" in cells[0].lower():
            header_seen = True
            layout.setdefault(current_section, {"columns": [], "raw": ""})
            continue

        if not header_seen:
            continue

        col = cells[0].replace("\\|", "|").strip()
        if col and col.lower() != "column header":
            layout[current_section]["columns"].append(col)

    return layout


# ── Requirements ───────────────────────────────────────────────────────────────

def _parse_requirements(text: str) -> list:
    """Return list of {id, status, type, text} dicts from bullet lines."""
    reqs = []
    for m in re.finditer(r"^\s*-\s+(.+)$", text, re.MULTILINE):
        txt = m.group(1).strip()
        # Skip comment lines, formatting notes, and very short lines
        if not txt or len(txt) < 8:
            continue
        if txt.startswith(("*", "[", "|", ">")):
            continue
        reqs.append({"id": None, "status": None, "type": None, "text": txt})
    return reqs


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_spec(md_path: str) -> dict:
    """
    Parse a spec .md file into a report dict compatible with:
        rdl_generator.generate_rdl(report)
        pbip_generator.generate_pbip(report, output_dir)

    Confirmed values from the spec (model name, connection string, SQL) are
    injected as underscore-prefixed keys so the generators prefer them over
    auto-inferred values:
        _spec_model            — confirmed semantic model name
        _spec_connect_string   — full connection string from spec
        _spec_datasource_name  — datasource name (WorkspaceSlug_ModelName)
        _spec_guid             — dataset GUID
        _spec_sql              — SQL query from Datasets section
    """
    text = Path(md_path).read_text(encoding="utf-8")

    # Report name from H1 heading
    title_m = re.search(
        r"^# (?:RDL Report Spec|Report Spec):\s*(.+)$", text, re.MULTILINE
    )
    report_name = (
        title_m.group(1).strip()
        if title_m
        else Path(md_path).stem.replace("-", " ").title()
    )

    sections = _split_sections(text)

    meta    = _parse_metadata(sections.get("Metadata", ""))
    ds_info = _parse_datasource(sections.get("Data Source", ""))

    # Parameters vs Filters — spec has one or the other, not both
    params_text  = sections.get("Parameters", "")
    filters_text = sections.get("Filters", "")

    if filters_text:
        filters    = _parse_filters(filters_text)
        # Flatten filters into parameters list for RDL ReportParameter generation
        parameters = [
            {
                "label":    f["label"],
                "required": f["required"],
                "select":   f["select"],
                "notes":    f.get("notes", ""),
            }
            for f in filters
        ]
    else:
        filters    = []
        parameters = _parse_parameters(params_text)

    sql    = _parse_sql(sections.get("Datasets", ""))
    layout = _parse_layout(sections.get("Layout", ""))
    reqs   = _parse_requirements(
        sections.get("Business Rules / Requirements", "")
        or sections.get("Business Rules", "")
    )

    # Normalise report format
    fmt_raw = meta.get("format", "")
    if re.search(r"paginated|\.rdl", fmt_raw, re.I):
        report_format = "Paginated"
    elif re.search(r"visual|\.pbip|power\s*bi", fmt_raw, re.I):
        report_format = "Visual"
    else:
        report_format = "Paginated"   # safe default — most FRD reports are paginated

    report: dict = {
        "name":           report_name,
        "report_format":  report_format,
        "folder":         meta.get("folder", "Output"),
        "target_folder":  meta.get("folder", "Output"),
        "legacy_reports": meta.get("legacy_path", ""),
        "legacy_users":   meta.get("legacy_users", ""),
        "summary":        meta.get("description", ""),
        "sort":           meta.get("sort", ""),
        "notes":          meta.get("notes", ""),
        "datasource_type": ds_info.get("type", "semantic_model"),
        "parameters":     parameters,
        "filters":        filters,
        "layout":         layout,
        "requirements":   reqs,
    }

    # Inject spec overrides — generators check these before auto-inferring
    if ds_info.get("semantic_model"):
        report["_spec_model"] = ds_info["semantic_model"]
    if ds_info.get("connect_string"):
        report["_spec_connect_string"] = ds_info["connect_string"]
    if ds_info.get("datasource_name"):
        report["_spec_datasource_name"] = ds_info["datasource_name"]
    if ds_info.get("guid"):
        report["_spec_guid"] = ds_info["guid"]
    if sql:
        report["_spec_sql"] = sql

    return report
