"""
frd_parser.py
Parses a Performance Wizard FRD (.docx) into structured JSON.
Each report is extracted from Azure DevOps SDT content controls embedded in the Word doc.

Improvements over reference implementation:
- Robust column splitting with known multi-word column name awareness
- Structured filter parsing with fallback to raw text
- Better format detection including "Power BI" / "paginated" keywords
- Cleans zero-width space artifacts from Word
"""

import re
import json
import argparse
from pathlib import Path
import docx
from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Zero-width and non-breaking space cleanup
_ZWS = re.compile(r"[\u200b\u200c\u200d\ufeff\xa0]+")


def _attr(elem, local):
    return elem.get(f"{{{W}}}{local}", "")


def _clean_ws(text: str) -> str:
    """Strip zero-width spaces and normalize whitespace."""
    return _ZWS.sub(" ", text).strip()


def extract_sdt_text(sdt_elem):
    """Extract visible text from an SDT element, skipping vanished (hidden) runs."""
    texts = []
    for content in sdt_elem.findall(".//w:sdtContent", NS):
        for r in content.findall(".//w:r", NS):
            rpr = r.find("w:rPr", NS)
            is_vanish = rpr is not None and rpr.find("w:vanish", NS) is not None
            if not is_vanish:
                t = r.find("w:t", NS)
                if t is not None and t.text:
                    texts.append(t.text)
    return _clean_ws("".join(texts))


def clean_workitem_text(raw: str) -> str:
    """Strip ADO work item header/footer noise from SDT text."""
    raw = re.sub(r"^MO-\d+,\s*\w+,\s*[\w/]+\s*-\s*", "", raw).strip()
    raw = re.sub(r"\s*MO-\d+,\s*\w+,\s*[\w/]+\s*-\s*MO-\d+\w*\s*$", "", raw).strip()
    raw = re.sub(r"\s*MO-\d+\w*\s*$", "", raw).strip()
    return _clean_ws(raw)


def parse_summary(raw: str) -> dict:
    """Parse the flat summary SDT text into a structured dict."""
    raw = re.sub(r"^MO-\d+,\s*\w+,\s*[\w/]+\s*-", "", raw).strip()
    raw = re.sub(r"\s*MO-\d+,\s*\w+,\s*[\w/]+\s*-\s*MO-\d+\w*\s*$", "", raw).strip()
    raw = re.sub(r"\s*MO-\d+\w*\s*$", "", raw).strip()
    raw = _clean_ws(raw)

    fields = [
        "Report Title", "Legacy Report(s)", "Legacy Users", "Summary",
        "Report Format", "Sort", "New Folder", "Folder", "Notes",
    ]
    result = {}
    # Longest-first to avoid 'Folder' matching inside 'New Folder'
    sorted_fields = sorted(fields, key=len, reverse=True)
    pattern = "|".join(re.escape(f) + r"(?=\b|[^a-z])" for f in sorted_fields)
    parts = re.split(f"({pattern})", raw)
    current_key = None
    for part in parts:
        stripped = _clean_ws(part)
        if not stripped:
            continue
        if stripped in fields:
            current_key = stripped
        elif current_key:
            result[current_key] = stripped.lstrip(":").strip()
            current_key = None
    return result


def parse_parameters(raw_list: list) -> list:
    """Parse parameter SDT text into list of parameter dicts."""
    params = []
    for raw in raw_list:
        text = clean_workitem_text(raw)
        text = re.sub(
            r"Parameter\s+Label\s*Single\s*/\s*Multiple\s+Select\s*Notes?", "", text
        ).strip()
        if not text or text.upper() in ("N/A", "--", "NONE"):
            continue
        rows = re.findall(
            r"([A-Z][^\n]+?)\s+(Single|Multiple)\s*(.*?)(?=\s+[A-Z][^\n]+?\s+(?:Single|Multiple)|$)",
            text,
            re.DOTALL,
        )
        for label, select, notes in rows:
            label = _clean_ws(label)
            required = label.endswith("*")
            params.append({
                "label": label.rstrip("*").strip(),
                "required": required,
                "select": select.strip(),
                "notes": _clean_ws(notes),
            })
        if not rows and text:
            params.append({"raw": text})
    return params


def parse_filters(raw_list: list) -> list:
    """Parse filter SDT text into list of filter dicts."""
    filters = []
    for raw in raw_list:
        text = clean_workitem_text(raw)
        text = re.sub(
            r"Filter\s+Label\s*Filter\s+Type\s*Filter\s+Context\s*Single\s*/\s*Multiple\s+Select\s*Notes?",
            "", text
        ).strip()
        if not text or text.upper() in ("N/A", "--", "NONE"):
            continue
        rows = re.findall(
            r"([A-Z][^\n]+?)\s+(Global|Page|Local)\s+([^\n]+?)\s+(Single|Multiple)\s*(.*?)(?=\s+[A-Z][^\n]+?\s+(?:Global|Page|Local)|$)",
            text,
            re.DOTALL,
        )
        for label, ftype, ctx, select, notes in rows:
            label = _clean_ws(label)
            required = label.endswith("*")
            filters.append({
                "label": label.rstrip("*").strip(),
                "required": required,
                "filter_type": ftype.strip(),
                "context": _clean_ws(ctx),
                "select": select.strip(),
                "notes": _clean_ws(notes),
            })
        if not rows and text:
            filters.append({"raw": text})
    return filters


def parse_layout(raw_list: list) -> dict:
    """
    Parse layout SDT text.
    Returns dict of {section_name: {"columns": [...], "raw": str}}.
    Section names come from <Tab N, Name>, <Page N, Name>, <Table N> markers.
    """
    all_text = " ".join(clean_workitem_text(r) for r in raw_list)
    all_text = _clean_ws(all_text)
    if not all_text:
        return {}

    all_text = re.sub(
        r"The columns included in the report are defined below\.?\s*", "", all_text
    ).strip()

    sections = re.split(r"(<(?:Tab|Page|Table)[^>]*>|<Layout Continued>)", all_text)
    result = {}
    current_section = "main"
    buffer_parts = []

    for part in sections:
        part = part.strip()
        if not part:
            continue
        if re.match(r"^<.*>$", part):
            if buffer_parts:
                raw_cols = " ".join(buffer_parts).strip()
                result[current_section] = {
                    "columns": _split_columns(raw_cols),
                    "raw": raw_cols,
                }
                buffer_parts = []
            label = part.strip("<>").strip()
            if label == "Layout Continued":
                current_section = f"{current_section} (continued)"
            else:
                current_section = label
        else:
            buffer_parts.append(part)

    if buffer_parts:
        raw_cols = " ".join(buffer_parts).strip()
        result[current_section] = {
            "columns": _split_columns(raw_cols),
            "raw": raw_cols,
        }

    return result


def _split_columns(text: str) -> list:
    """
    Split a run-together column string into individual column names.
    Inserts a split before each uppercase letter that follows a lowercase/digit/punctuation.
    Also splits on <...> template markers.
    """
    # Strip <...> template markers (totals/averages placeholders)
    text = re.sub(r"<[^>]+>", " ", text)
    # Insert | before each apparent new column boundary
    spaced = re.sub(r"(?<=[a-z0-9\.\)%])(?=[A-Z])", "|", text)
    # Also split on # followed by a space then uppercase
    cols = [c.strip() for c in spaced.split("|") if c.strip()]
    # Filter obvious noise
    return [c for c in cols if len(c) > 1 and c not in ("N/A", "--")]


def parse_requirements(raw_list: list) -> list:
    """Return list of requirement dicts with ADO work item ID and text."""
    reqs = []
    for raw in raw_list:
        raw = _clean_ws(raw)
        match = re.match(r"(MO-\d+),\s*(\w+),\s*([\w/]+)\s*-\s*(.*)", raw, re.DOTALL)
        if match:
            work_item_id, status, req_type, text = match.groups()
            text = re.sub(r"\s*MO-\d+,\s*\w+,\s*[\w/]+\s*-\s*MO-\d+\w*\s*$", "", text).strip()
            text = re.sub(r"\s*MO-\d+\w*\s*$", "", _clean_ws(text)).strip()
            reqs.append({
                "id": work_item_id,
                "status": status,
                "type": req_type,
                "text": text,
            })
        elif raw.strip():
            reqs.append({"id": None, "status": None, "type": None, "text": raw.strip()})
    return reqs


def _infer_datasource(report: dict) -> str:
    """
    Infer whether this report uses a semantic model or a direct DB connection.
    Returns 'semantic_model', 'db2', or 'snowflake'.
    """
    text = " ".join([
        report.get("summary", ""),
        report.get("notes", ""),
        report.get("legacy_reports", ""),
        report.get("name", ""),
    ]).lower()
    # Reports with these keywords likely come from a raw DB
    if any(k in text for k in ["boadb", "db2", "ardb", "1042", "tax report"]):
        return "db2"
    if "snowflake" in text:
        return "snowflake"
    return "semantic_model"


def parse_frd(docx_path: str) -> dict:
    """Main entry point. Returns dict with metadata and list of reports."""
    doc = docx.Document(docx_path)
    reports = {}
    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    current_report = None
    skip_sections = {"Introduction", "Performance Wizard Reporting"}

    for elem in doc.element.body.iter():
        tag = elem.tag.split("}")[-1]

        if tag == "p":
            style_elem = elem.find(".//w:pStyle", NS)
            if style_elem is None:
                continue
            style = _attr(style_elem, "val")
            text_parts = []
            for r in elem.findall("w:r", NS):
                t = r.find("w:t", NS)
                if t is not None and t.text:
                    text_parts.append(t.text)
            text = _clean_ws("".join(text_parts))
            if not text:
                continue

            if style == "Heading1":
                current_h1 = text
                current_h2 = ""
                current_h3 = ""
                current_report = None
            elif style == "Heading2":
                current_h2 = text
                current_h3 = ""
                if current_h1 not in skip_sections:
                    key = f"{current_h1}::{current_h2}"
                    if key not in reports:
                        reports[key] = {
                            "folder": current_h1,
                            "name": current_h2,
                            "_summary_raw": None,
                            "_params_raw": [],
                            "_filters_raw": [],
                            "_layout_raw": [],
                            "_requirements_raw": [],
                        }
                    current_report = reports[key]
            elif style == "Heading3":
                current_h3 = text

        elif tag == "sdt":
            alias = elem.find(".//w:alias", NS)
            alias_val = _attr(alias, "val") if alias is not None else ""
            if alias_val == "Work Item" and current_report is not None:
                raw_text = extract_sdt_text(elem)
                if raw_text:
                    sec = current_h3.lower()
                    if "summary" in sec:
                        current_report["_summary_raw"] = raw_text
                    elif "parameter" in sec:
                        current_report["_params_raw"].append(raw_text)
                    elif "filter" in sec:
                        current_report["_filters_raw"].append(raw_text)
                    elif "layout" in sec:
                        current_report["_layout_raw"].append(raw_text)
                    elif "requirement" in sec:
                        current_report["_requirements_raw"].append(raw_text)

    # Second pass: structure each report
    structured = []
    for report in reports.values():
        summary = parse_summary(report.get("_summary_raw") or "")

        # Normalize report format
        fmt_raw = summary.get("Report Format", "").strip()
        if re.search(r"paginated|\.rdl", fmt_raw, re.IGNORECASE):
            report_format = "Paginated"
        elif re.search(r"visual|power\s*bi|\.pbip", fmt_raw, re.IGNORECASE):
            report_format = "Visual"
        elif fmt_raw:
            report_format = fmt_raw
        else:
            report_format = "Unknown"

        entry = {
            "folder": report["folder"],
            "name": report["name"],
            "report_format": report_format,
            "legacy_reports": summary.get("Legacy Report(s)", ""),
            "legacy_users": summary.get("Legacy Users", ""),
            "summary": summary.get("Summary", ""),
            "sort": summary.get("Sort", ""),
            "target_folder": summary.get("New Folder") or summary.get("Folder", ""),
            "notes": re.sub(r"\s*MO-\d+[,\w]*\s*$", "", summary.get("Notes", "")).strip(),
            "parameters": parse_parameters(report["_params_raw"]),
            "filters": parse_filters(report["_filters_raw"]),
            "layout": parse_layout(report["_layout_raw"]),
            "requirements": parse_requirements(report["_requirements_raw"]),
        }
        entry["datasource_type"] = _infer_datasource(entry)
        structured.append(entry)

    paginated = sum(1 for r in structured if r["report_format"] == "Paginated")
    visual = sum(1 for r in structured if r["report_format"] == "Visual")
    unknown = sum(1 for r in structured if r["report_format"] == "Unknown")

    return {
        "source_file": Path(docx_path).name,
        "total_reports": len(structured),
        "paginated_count": paginated,
        "visual_count": visual,
        "unknown_count": unknown,
        "reports": structured,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a Performance Wizard FRD into JSON")
    parser.add_argument("docx", help="Path to the FRD .docx file")
    parser.add_argument("-o", "--output", default="output/json/frd_parsed.json")
    args = parser.parse_args()

    result = parse_frd(args.docx)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Parsed {result['total_reports']} reports → {out_path}")
    print(f"  Paginated: {result['paginated_count']}")
    print(f"  Visual:    {result['visual_count']}")
    if result.get("unknown_count"):
        print(f"  Unknown:   {result['unknown_count']}")
