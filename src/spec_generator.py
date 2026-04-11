"""
spec_generator.py — Generate structured .md spec files from the FRD .docx.

All parsing and rendering logic lives here; no external skill dependency.

Standalone CLI usage:
    python src/spec_generator.py "path/to/FRD.docx"
    python src/spec_generator.py "path/to/FRD.docx" --report "Daily Sales"
    python src/spec_generator.py "path/to/FRD.docx" --list
    python src/spec_generator.py "path/to/FRD.docx" --output-dir ./specs

Library usage (from generate_all.py):
    from src.spec_generator import generate_all_specs
    generate_all_specs(frd_path, output_dir)

Requires: pip install python-docx
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import docx
    from docx.text.paragraph import Paragraph
except ImportError:
    print("ERROR: python-docx is required.  Install with:  pip install python-docx")
    sys.exit(1)

try:
    from src.config import cfg as _cfg
except ImportError:
    try:
        from config import cfg as _cfg
    except ImportError:
        _cfg = None

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ── Datasource inference ───────────────────────────────────────────────────────

def _infer_ds_info(report_name: str, summary: dict) -> tuple:
    """Return (datasource_type, semantic_model) for a report using cfg keywords."""
    report = {
        "name":    report_name,
        "summary": summary.get("description", ""),
        "notes":   summary.get("notes", ""),
    }
    if _cfg is not None:
        ds_type = _cfg.infer_datasource(report)
        model = _cfg.infer_semantic_model(report) if ds_type == "semantic_model" else ""
    else:
        ds_type = "semantic_model"
        model = "TODO_SemanticModel"
    return ds_type, model


# ── Text cleaning ──────────────────────────────────────────────────────────────

_JIRA_NOISE = re.compile(
    r"Missouri_Omnia_Conversion/MO-\d+"
    r"|MO-\d+"
    r"|[,]+\s*Draft\s*(?:Draft)?"
    r"|[,]+\s*Functional\s*(?:Functional)?"
    r"|[,]+\s*Business\s*(?:Business)?"
    r"|\s*,\s*,\s*-\s*-\s*"
    r"|\s*,\s*-\s*-\s*"
    r"|\s+-\s+-(?:\s+|$)"
    r"|[\u200b\u200c\u200d\u00ad\ufeff]+"
)


def clean_raw(raw: str) -> str:
    text = _JIRA_NOISE.sub(" ", raw)
    text = re.sub(r"\s*,\s*,\s*", " ", text)
    return " ".join(text.split()).strip()


def deduplicate(text: str) -> str:
    """
    Word SDT controls triple-stamp their content as a cross-reference artifact.
    Detect and return only the first copy.
    """
    if not text or len(text) < 4:
        return text
    n = len(text)

    # Fast path: exact prefix immediately repeats ("RegionRegionRegion")
    for end in range(2, n // 2 + 1):
        prefix = text[:end].strip()
        nxt = text[end: end * 2].strip()
        if prefix and len(prefix) >= 2 and nxt == prefix:
            return prefix

    # Slow path: first reoccurrence of the leading fragment
    max_w = min(250, n // 2)
    for w in range(max_w, 8, -1):
        fragment = text[:w].strip()
        if not fragment:
            continue
        pos = text.find(fragment, w // 2)
        if 0 < pos <= n * 2 // 3:
            return text[:pos].strip()

    return text


def clean_cell(raw: str) -> str:
    return deduplicate(clean_raw(raw))


# ── Element helpers ────────────────────────────────────────────────────────────

def paras_in(element) -> list:
    results = []
    for p in element.iter(f"{{{NS_W}}}p"):
        txt = clean_cell("".join(p.itertext()))
        if txt and len(txt) > 1:
            results.append(txt)
    return results


def table_rows_in(element) -> list:
    rows = []
    for tr in element.iter(f"{{{NS_W}}}tr"):
        cells = [
            clean_cell("".join(tc.itertext()))
            for tc in tr.iter(f"{{{NS_W}}}tc")
        ]
        if any(c for c in cells):
            rows.append(cells)
    return rows


# ── Document parsing ───────────────────────────────────────────────────────────

def build_item_list(doc) -> list:
    items = []
    body = doc.element.body
    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            try:
                para = Paragraph(child, doc)
                items.append({
                    "type":  "para",
                    "style": para.style.name,
                    "text":  para.text.strip(),
                    "el":    child,
                })
            except Exception:
                items.append({"type": "para", "style": "Normal", "text": "", "el": child})
        elif tag == "sdt":
            items.append({"type": "sdt", "style": "", "text": "", "el": child})
        else:
            items.append({"type": "other", "style": "", "text": "", "el": child})
    return items


# ── Boundary detection ─────────────────────────────────────────────────────────

def find_report_ranges(items: list) -> list:
    """
    Return [(report_name, start_idx, end_idx), ...] for every Heading-2
    that has a 'Summary' Heading-3 as its first H3 sub-section.
    """
    h2_headings = [
        (it["text"], i)
        for i, it in enumerate(items)
        if it["type"] == "para" and it.get("style", "") == "Heading 2" and it["text"]
    ]
    ranges = []
    for j, (text, idx) in enumerate(h2_headings):
        end_idx = h2_headings[j + 1][1] if j + 1 < len(h2_headings) else len(items)
        has_summary = any(
            items[k]["type"] == "para"
            and items[k]["style"] == "Heading 3"
            and items[k]["text"] == "Summary"
            for k in range(idx, min(idx + 10, end_idx))
        )
        if has_summary:
            ranges.append((text.strip(), idx, end_idx))
    return ranges


def subsection_sdts(items: list, h2_start: int, h2_end: int, section_name: str) -> list:
    h3_idx = None
    for i in range(h2_start, h2_end):
        it = items[i]
        if (
            it["type"] == "para"
            and it["style"] == "Heading 3"
            and it["text"] == section_name
        ):
            h3_idx = i
            break
    if h3_idx is None:
        return []

    end = h2_end
    for i in range(h3_idx + 1, h2_end):
        it = items[i]
        if (
            it["type"] == "para"
            and it["style"] in ("Heading 2", "Heading 3")
            and it["text"]
        ):
            end = i
            break

    return [items[i]["el"] for i in range(h3_idx + 1, end) if items[i]["type"] == "sdt"]


# ── Section extractors ─────────────────────────────────────────────────────────

_SUMMARY_KEYS = {
    "report title":  "title",
    "legacy report": "legacy_path",
    "legacy users":  "legacy_users",
    "summary":       "description",
    "report format": "format",
    "sort":          "sort",
    "new folder":    "folder",
    "folder":        "folder",
    "notes":         "notes",
}


def extract_summary(sdts: list) -> dict:
    if not sdts:
        return {}
    sdt = sdts[0]
    result = {}

    for row in table_rows_in(sdt):
        if not row:
            continue
        label_raw = row[0].lower().strip()
        for key_frag, field in _SUMMARY_KEYS.items():
            if label_raw == key_frag or label_raw.startswith(key_frag):
                val = row[1].strip() if len(row) > 1 else ""
                if field not in result:
                    result[field] = val
                break

    if len(result) < 3:
        flat = " ".join(paras_in(sdt))
        for label, field in {
            "Summary": "description",
            "Report Format": "format",
            "New Folder": "folder",
            "Folder": "folder",
            "Notes": "notes",
            "Legacy Users": "legacy_users",
        }.items():
            if field in result:
                continue
            anchors = "|".join(
                re.escape(k)
                for k in ["Report Title", "Legacy Report", "Legacy Users",
                           "Summary", "Report Format", "Sort",
                           "New Folder", "Folder", "Notes"]
            )
            m = re.search(
                re.escape(label) + r"[\s:]+(.*?)(?=" + anchors + r"|$)",
                flat, re.IGNORECASE,
            )
            if m:
                result[field] = m.group(1).strip()

    return result


def extract_params(sdts: list) -> list:
    if not sdts:
        return []
    rows = table_rows_in(sdts[0])
    params = []
    is_filter_table = False
    for row in rows:
        if not row or not row[0].strip():
            continue
        label_lc = row[0].lower()
        if "filter label" in label_lc:
            is_filter_table = True
            continue
        if "parameter label" in label_lc:
            is_filter_table = False
            continue
        if is_filter_table:
            params.append({
                "label":   row[0],
                "type":    row[1] if len(row) > 1 else "",
                "context": row[2] if len(row) > 2 else "",
                "select":  row[3] if len(row) > 3 else "",
                "notes":   row[4] if len(row) > 4 else "",
            })
        else:
            params.append({
                "label":  row[0],
                "select": row[1] if len(row) > 1 else "",
                "notes":  row[2] if len(row) > 2 else "",
            })
    return params


_SKIP_CELL = re.compile(
    r"^(<layout continued>|<total>|total:|[\s\u200b]+)$", re.IGNORECASE
)


def extract_layout(sdts: list) -> list:
    if not sdts:
        return []
    groups = []
    current_tab = None
    current_cols = []

    def flush():
        nonlocal current_tab, current_cols
        if current_cols:
            groups.append({"tab": current_tab, "columns": list(current_cols)})
        current_tab = None
        current_cols = []

    _inline_tab = re.compile(
        r"(Tab\s*\d+\s*\([^)]+\)|Tab\s*\d+\s*[^,:\n]+?)\s*:", re.IGNORECASE
    )

    def _handle_para_text(txt):
        nonlocal current_tab, current_cols
        txt = txt.strip()
        if not txt:
            return
        if re.match(r"^Tab\s*\d+", txt, re.IGNORECASE):
            flush()
            current_tab = re.sub(r"[\s:,]+$", "", txt).strip()
            return
        for m in _inline_tab.finditer(txt):
            label = re.sub(r"[\s:,]+$", "", m.group(1)).strip()
            if not current_cols:
                current_tab = label
            elif label != current_tab:
                flush()
                current_tab = label

    def _handle_cell(cell):
        nonlocal current_tab, current_cols
        cell = cell.strip()
        if not cell or _SKIP_CELL.match(cell):
            return
        if len(cell) > 80:
            return
        if cell.startswith("<") and cell.endswith(">"):
            inner = cell[1:-1].strip()
            if inner and "total" not in inner.lower() and "avg" not in inner.lower():
                flush()
                current_tab = f"Group by: {inner}"
        else:
            current_cols.append(cell)

    for sdt in sdts:
        for child in sdt.iter():
            tag = child.tag.split("}")[-1]
            if tag == "p":
                parent_tag = (
                    child.getparent().tag.split("}")[-1]
                    if child.getparent() is not None else ""
                )
                if parent_tag not in ("tc", "tr"):
                    txt = clean_cell("".join(child.itertext()))
                    if txt:
                        _handle_para_text(txt)
            elif tag == "tr":
                for tc in child.iter(f"{{{NS_W}}}tc"):
                    cell_txt = clean_cell("".join(tc.itertext()))
                    _handle_cell(cell_txt)

    flush()
    return groups


def extract_requirements(sdts: list) -> list:
    reqs = []
    for sdt in sdts:
        for para in paras_in(sdt):
            if para and len(para) > 8 and not re.match(r"^[\s-]+$", para):
                reqs.append(para)
                break
    return reqs


# ── General requirements (section 2.1) ────────────────────────────────────────

def extract_general_reqs(items: list) -> dict:
    result = {
        "all_reports":  [],
        "paginated":    [],
        "visual":       [],
        "data_formats": [],
    }

    all_headings = [
        (it["style"], it["text"], i)
        for i, it in enumerate(items)
        if it["type"] == "para" and "Heading" in it.get("style", "") and it["text"]
    ]

    def h2_range(fragment):
        for j, (style, text, idx) in enumerate(all_headings):
            if style == "Heading 2" and fragment.lower() in text.lower():
                end = all_headings[j + 1][2] if j + 1 < len(all_headings) else len(items)
                return idx, end
        return None, None

    def h3_sdts_in_range(h2_start, h2_end, h3_name):
        for i in range(h2_start, h2_end):
            it = items[i]
            if (it["type"] == "para"
                    and it["style"] == "Heading 3"
                    and it["text"] == h3_name):
                end = h2_end
                for k in range(i + 1, h2_end):
                    if (items[k]["type"] == "para"
                            and items[k]["style"] in ("Heading 3", "Heading 2")
                            and items[k]["text"]):
                        end = k
                        break
                return [items[m]["el"] for m in range(i + 1, end)
                        if items[m]["type"] == "sdt"]
        return []

    start, end = h2_range("General Requirements")
    if start is not None:
        for section, key in [
            ("All Reports",       "all_reports"),
            ("Paginated Reports", "paginated"),
            ("Visual Reports",    "visual"),
        ]:
            for sdt in h3_sdts_in_range(start, end, section):
                for p in paras_in(sdt):
                    if (p and len(p) > 8
                            and not p.lower().startswith(section.lower())
                            and not p.lower().startswith("performance wizard")
                            and not re.match(r"^[-\s]+$", p)):
                        result[key].append(p)

    start, end = h2_range("Jurisdiction")
    if start is not None:
        for i in range(start, end):
            it = items[i]
            if (it["type"] == "para"
                    and it["style"] == "Heading 4"
                    and it["text"] == "All Reports"):
                fmt_end = end
                for k in range(i + 1, end):
                    if (items[k]["type"] == "para"
                            and items[k]["style"] in ("Heading 4", "Heading 3", "Heading 2")
                            and items[k]["text"]):
                        fmt_end = k
                        break
                for m in range(i + 1, fmt_end):
                    if items[m]["type"] == "sdt":
                        for p in paras_in(items[m]["el"]):
                            if (p and len(p) > 5
                                    and not p.lower().startswith("performance wizard")
                                    and not re.match(r"^[-\s]+$", p)):
                                result["data_formats"].append(p)
                break

    return result


# ── Format inference ───────────────────────────────────────────────────────────

def infer_format(col: str) -> tuple:
    """Return (DataType, format_string, alignment) inferred from column name."""
    c = col.lower()
    if any(k in c for k in ["count", "qty", "quantity"]) and "no." not in c:
        return "Integer", "0,000 / (0,000)", "Right"
    if any(k in c for k in [
        "sales", "amount", "total", "cashless", "promo", "commission",
        "reinvestment", "validation", "gross", "cancel", "discount",
        "wager", "price", "revenue", "payment", "balance", "avg.",
    ]):
        return "Decimal", "$0,000.00 / ($0,000.00)", "Right"
    if "date" in c:
        return "DateTime", "MM/DD/YYYY", "Center"
    if any(k in c for k in [" id", "type", "zip", "phone", "no.", "number", "code", "bin"]):
        return "String", "as-stored", "Center"
    if any(k in c for k in [
        "name", "address", "city", "street", "description", "region",
        "district", "manager", "contact", "title", "folder", "path",
    ]):
        return "String", "—", "Left"
    return "String", "—", "Left"


# ── Markdown renderer ──────────────────────────────────────────────────────────

def generate_md(
    report_name: str,
    summary: dict,
    params: list,
    layout: list,
    reqs: list,
    gen_reqs: dict,
    param_section: str,
    datasource_type: str = "semantic_model",
    semantic_model: str = "",
) -> str:
    lines = []
    title = summary.get("title") or report_name
    fmt = summary.get("format") or "Paginated"
    is_paginated = "paginated" in fmt.lower()
    file_ext = ".rdl" if is_paginated else ".pbip"

    lines += [f"# RDL Report Spec: {title}", ""]

    lines += ["## Metadata", ""]
    if summary.get("legacy_path"):
        lines.append(f"- **Legacy Path:** `{summary['legacy_path']}`")
    if summary.get("legacy_users"):
        lines.append(f"- **Legacy Users:** {summary['legacy_users']}")
    if summary.get("description"):
        lines.append(f"- **Description:** {summary['description']}")
    lines.append(f"- **Report Format:** {fmt} ({file_ext})")
    if summary.get("folder"):
        lines.append(f"- **Output Folder:** {summary['folder']}")
    sort_val = (summary.get("sort") or "").strip()
    if sort_val and sort_val.upper() not in ("N/A", ""):
        lines.append(f"- **Sort:** {sort_val}")
    if summary.get("notes"):
        lines.append(f"- **Notes:** {summary['notes']}")
    lines.append("")

    lines += ["## Data Source", ""]
    if datasource_type == "db2":
        db2_dsn = _cfg.db2_dsn if _cfg else "MOS-Q1-BOADB"
        db2_src = _cfg.db2_source_name if _cfg else "BOADB"
        safe = re.sub(r"[^\w\s\-]", "", report_name).strip().replace(" ", "_")
        lines += [
            "- **Type:** DB2 / ARDB (ODBC)",
            f"- **Source Name:** `{db2_src}`",
            f"- **DSN:** `{db2_dsn}`",
            f"- **SQL:** hand-authored — `sql/{safe}.sql`",
            "  *(place hand-authored SQL at this path; generator falls back to auto-stub if absent)*",
        ]
    elif datasource_type == "snowflake":
        sf_dsn = _cfg.sfodbc_dsn if _cfg else "MOS-PX-SFODBC"
        sf_src = _cfg.sfodbc_source_name if _cfg else "LPC_E2_SFODBC"
        safe = re.sub(r"[^\w\s\-]", "", report_name).strip().replace(" ", "_")
        lines += [
            "- **Type:** Snowflake (ODBC)",
            f"- **Source Name:** `{sf_src}`",
            f"- **DSN:** `{sf_dsn}`",
            "- **Schemas:** `TXNDTL`, `DIMCORE`",
            f"- **SQL:** hand-authored — `sql/{safe}.sql`",
            "  *(place hand-authored SQL at this path; generator falls back to auto-stub if absent)*",
        ]
    else:
        model = semantic_model or "TODO_SemanticModel"
        lines += [
            "- **Type:** Semantic Model (Power BI Dataset)",
            f"- **Model:** `{model}`",
            "- **Connection:** shared Fabric semantic model (no direct SQL)",
        ]
    lines.append("")

    lines += [f"## {param_section}", ""]
    if params:
        is_filter = any("type" in p for p in params)
        if is_filter:
            lines.append("| Label | Filter Type | Context | Single / Multiple | Default / Notes |")
            lines.append("|---|---|---|---|---|")
            for p in params:
                label   = p.get("label", "").replace("|", "\\|")
                ftype   = p.get("type", "").replace("|", "\\|")
                context = p.get("context", "").replace("|", "\\|")
                select  = p.get("select", "").replace("|", "\\|")
                notes   = p.get("notes", "").replace("|", "\\|")
                lines.append(f"| {label} | {ftype} | {context} | {select} | {notes} |")
        else:
            lines.append("| Label | Single / Multiple | Default / Notes |")
            lines.append("|---|---|---|")
            for p in params:
                label  = p["label"].replace("|", "\\|")
                select = p["select"].replace("|", "\\|")
                notes  = p["notes"].replace("|", "\\|")
                lines.append(f"| {label} | {select} | {notes} |")
    else:
        lines.append("_None defined._")
    lines.append("")

    param_names = (
        ", ".join(
            "@" + re.sub(r"[^a-zA-Z0-9]", "", p["label"].rstrip("*"))
            for p in params
        )
        if params else "none"
    )
    lines += [
        "## Datasets", "",
        "### ds_Main",
        f"- **Parameters:** {param_names}",
        "- **Query:** *(SQL to be provided — see Business Rules section below)*",
        "- **Fields:** *(derived from Layout section below)*",
        "",
    ]

    lines += ["## Layout", ""]
    if layout:
        for group in layout:
            tab_name = group["tab"]
            cols = group["columns"]
            if tab_name:
                lines += [f"### {tab_name}", ""]
            if cols:
                lines.append("| Column Header | Field | DataType | Format | Alignment |")
                lines.append("|---|---|---|---|---|")
                for col in cols:
                    field = re.sub(r"[^a-zA-Z0-9]+", "_", col).strip("_")
                    dtype, fmt_str, align = infer_format(col)
                    lines.append(f"| {col} | {field} | {dtype} | {fmt_str} | {align} |")
                lines.append("")
    else:
        lines += ["_Layout not specified._", ""]

    lines += ["## Business Rules / Requirements", ""]
    if reqs:
        for r in reqs:
            lines.append(f"- {r.rstrip('.')}.")
    else:
        lines += ["_No specific business rules defined._"]
    lines.append("")

    lines += ["## Header / Footer", ""]
    if is_paginated:
        param_labels = (
            ", ".join(p["label"] for p in params) if params else "N/A"
        )
        lines += [
            f"- **Report Header:** Report title + Parameters ({param_labels}) "
            f"+ Run date/time (MM/DD/YYYY HH:MM:SS)",
            "- **Report Footer:** Report title + Page X of Y",
        ]
    else:
        lines.append("- **Report Header:** Latest date of data availability")
    lines += ["- **Logo:** Missouri Lottery logo (top-left of header)", ""]

    lines += ["## General Formatting  *(Section 2.1 — applies to all reports)*", ""]
    merged_reqs = gen_reqs.get("all_reports", []) + (
        gen_reqs.get("paginated", []) if is_paginated else gen_reqs.get("visual", [])
    )
    for r in merged_reqs:
        lines.append(f"- {r}")
    if merged_reqs:
        lines.append("")

    lines.append("**Data formats:**")
    lines.append("")
    data_fmts = gen_reqs.get("data_formats", [])
    if data_fmts:
        for f_item in data_fmts:
            lines.append(f"- {f_item}")
    else:
        lines += [
            "- Date: `MM/DD/YYYY`",
            "- Time: `HH:MM:SS` (24-hour)",
            "- Currency: `$0,000.00` · negatives: `($0,000.00)` · zeros: `$0.00`",
            "- Counts: `0,000` · negatives: `(0,000)` · zeros: `0`",
            "- Phone: `123-456-7890`",
            "- Right-justified: currency and non-currency numbers",
            "- Centered: dates, codes, IDs, phone numbers",
            "- Left-justified: names, addresses, all other alphanumeric",
        ]
    lines.append("")
    return "\n".join(lines)


# ── Utilities ──────────────────────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip().lower())
    return name + ".md"


# ── Library API ────────────────────────────────────────────────────────────────

def generate_all_specs(frd_docx_path: str, output_dir: str) -> list:
    """
    Generate .md spec files for all reports in the FRD.

    Parameters
    ----------
    frd_docx_path : str
        Path to the FRD .docx file.
    output_dir : str
        Base output directory (specs go into <output_dir>/specs/).

    Returns
    -------
    list of str
        Paths of generated .md files.
    """
    specs_dir = Path(output_dir) / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    doc = docx.Document(str(frd_docx_path))
    items = build_item_list(doc)
    gen_reqs = extract_general_reqs(items)
    reports = find_report_ranges(items)

    generated = []
    for report_name, start, end in reports:
        try:
            param_sec = "Parameters"
            for i in range(start, min(start + 10, end)):
                it = items[i]
                if it["type"] == "para" and it["style"] == "Heading 3":
                    if it["text"] == "Filters":
                        param_sec = "Filters"
                        break

            summary = extract_summary(subsection_sdts(items, start, end, "Summary"))
            params  = extract_params(subsection_sdts(items, start, end, param_sec))
            layout  = extract_layout(subsection_sdts(items, start, end, "Layout"))
            reqs    = extract_requirements(subsection_sdts(items, start, end, "Requirements"))

            ds_type, model = _infer_ds_info(report_name, summary)
            md = generate_md(
                report_name, summary, params, layout, reqs, gen_reqs, param_sec,
                datasource_type=ds_type, semantic_model=model,
            )
            out_file = specs_dir / safe_filename(report_name)
            out_file.write_text(md, encoding="utf-8")
            generated.append(str(out_file))
        except Exception as exc:
            import traceback
            print(f"  ⚠  {report_name}: {exc}")
            traceback.print_exc()

    return generated


# ── Standalone CLI ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Generate .md spec files from a Performance Wizard FRD .docx"
    )
    ap.add_argument("docx_path", metavar="DOCX", help="Path to FRD .docx file")
    ap.add_argument("--output-dir", "-o",
                    help="Output directory (default: rdl-specs/ next to the docx)")
    ap.add_argument("--report", "-r",
                    help="Single report only (partial name match, case-insensitive)")
    ap.add_argument("--list", "-l", action="store_true",
                    help="List all reports found, then exit")
    ap.add_argument("--json", action="store_true",
                    help="Output report list as JSON (use with --list)")
    args = ap.parse_args()

    if not os.path.isfile(args.docx_path):
        print(f"ERROR: File not found: {args.docx_path}")
        sys.exit(1)

    doc = docx.Document(args.docx_path)
    items = build_item_list(doc)
    gen_reqs = extract_general_reqs(items)
    reports = find_report_ranges(items)

    if args.list:
        if args.json:
            print(json.dumps([r[0] for r in reports], indent=2))
        else:
            print(f"Found {len(reports)} reports:\n")
            for n, (name, _, _) in enumerate(reports, 1):
                print(f"  {n:3d}. {name}")
        return

    if args.report:
        reports = [(n, s, e) for n, s, e in reports if args.report.lower() in n.lower()]
        if not reports:
            print(f"ERROR: No report matching '{args.report}'")
            sys.exit(1)

    out_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(args.docx_path).parent / "rdl-specs"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out_dir}  ({len(reports)} report(s))\n")

    ok = err = 0
    for report_name, start, end in reports:
        try:
            param_sec = "Parameters"
            for i in range(start, min(start + 10, end)):
                it = items[i]
                if it["type"] == "para" and it["style"] == "Heading 3":
                    if it["text"] == "Filters":
                        param_sec = "Filters"
                        break

            summary = extract_summary(subsection_sdts(items, start, end, "Summary"))
            params  = extract_params(subsection_sdts(items, start, end, param_sec))
            layout  = extract_layout(subsection_sdts(items, start, end, "Layout"))
            reqs    = extract_requirements(subsection_sdts(items, start, end, "Requirements"))

            ds_type, model = _infer_ds_info(report_name, summary)
            md = generate_md(
                report_name, summary, params, layout, reqs, gen_reqs, param_sec,
                datasource_type=ds_type, semantic_model=model,
            )
            out_file = out_dir / safe_filename(report_name)
            out_file.write_text(md, encoding="utf-8")
            print(f"  ✓  {report_name}  →  {out_file.name}")
            ok += 1
        except Exception as exc:
            import traceback
            print(f"  ✗  {report_name}: {exc}")
            traceback.print_exc()
            err += 1

    print(f"\n{ok} generated, {err} errors  →  {out_dir}")


if __name__ == "__main__":
    main()

