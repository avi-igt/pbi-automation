"""
pbip_generator.py
Generates .pbip (Power BI Project) folder structure for visual reports.

Correct file layout (matches actual Power BI Desktop / Fabric output):

  ReportName.Report/
    definition.pbir           ← semantic model binding (byPath)
    definition/
      report.json             ← report-level metadata only (theme, settings)
      version.json            ← schema version
      pages/
        pages.json            ← page order + active page
        ReportSection1/       ← one folder per page
          page.json           ← page metadata (name, displayName, size)
          visuals/
            {visualId}/
              visual.json     ← individual visual definition
  ReportName.pbip             ← project artifact pointer

Key corrections over reference implementation:
- Separate files per page and per visual (not embedded in report.json)
- Correct visual.json projection format using 'field' key + 'queryRef'
- SourceRef uses 'Entity' (not 'Schema'+'Entity')
- definition.pbir uses byPath (not byConnection)
- report.json is metadata-only, not a page container
"""

import json
import re
import uuid
from pathlib import Path
from datetime import datetime

try:
    from report_generator.config import cfg as _cfg
except ImportError:
    try:
        from config import cfg as _cfg
    except ImportError:
        _cfg = None


def _get_cfg():
    return _cfg


# Visual type mapping: FRD section/column hints → Power BI visual type
_CHART_HINTS = {
    "lineChart": ["chart", "graph", "trend", "yoy", "monthly", "weekly", "daily", "comparison"],
    "barChart": ["bar", "top ", "bottom ", "rank", "by district", "by chain", "by region"],
    "pieChart": ["% of", "share", "distribution", "breakdown"],
    "card": ["kpi", "summary total", "manager", "total count", "grand total"],
}


def infer_visual_type(section_name: str, columns: list) -> str:
    """Heuristically pick a Power BI visual type from section name + columns."""
    text = (section_name + " " + " ".join(columns)).lower()
    for vtype, keywords in _CHART_HINTS.items():
        if any(kw in text for kw in keywords):
            return vtype
    return "tableEx"


def _visual_id() -> str:
    """Generate a 20-char hex visual ID matching PBI format."""
    return uuid.uuid4().hex[:20]


def _page_name(index: int) -> str:
    """Generate standard page section name."""
    return f"ReportSection{index + 1}" if index > 0 else "ReportSection1"


def make_column_projection(col_name: str, entity: str = "TODO_Table") -> dict:
    """Build a single column projection for a visual query state."""
    query_ref = f"{entity}.{col_name}"
    return {
        "field": {
            "Column": {
                "Expression": {
                    "SourceRef": {
                        "Entity": entity
                    }
                },
                "Property": col_name
            }
        },
        "queryRef": query_ref,
        "nativeQueryRef": col_name,
        "displayName": col_name
    }


def make_table_visual(visual_id: str, section_name: str, columns: list,
                      x: float, y: float, width: float, height: float) -> dict:
    """Build a tableEx visual.json dict."""
    c = _get_cfg()
    color_grid   = c.brand_color_grid   if c else "#D6DBEA"
    color_header = c.brand_color_header if c else "#FAFAFA"
    projections = [make_column_projection(col) for col in columns]
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x, "y": y, "z": 0,
            "height": height, "width": width,
            "tabOrder": 0
        },
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": projections
                    }
                }
            },
            "objects": {
                "grid": [{
                    "properties": {
                        "textSize": {"expr": {"Literal": {"Value": "8D"}}},
                        "gridHorizontalColor": {
                            "solid": {"color": {"expr": {"Literal": {"Value": f"'{color_grid}'"}}}}
                        }
                    }
                }],
                "columnHeaders": [{
                    "properties": {
                        "bold": {"expr": {"Literal": {"Value": "true"}}},
                        "backColor": {
                            "solid": {"color": {"expr": {"Literal": {"Value": f"'{color_header}'"}}}}
                        }
                    }
                }],
                "total": [{
                    "properties": {
                        "totals": {"expr": {"Literal": {"Value": "false"}}}
                    }
                }]
            },
            "visualContainerObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "false"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{section_name}'"}}},
                        "fontSize": {"expr": {"Literal": {"Value": "14D"}}},
                        "bold": {"expr": {"Literal": {"Value": "true"}}}
                    }
                }],
                "visualHeader": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "false"}}}
                    }
                }]
            },
            "drillFilterOtherVisuals": True
        }
    }


def make_chart_visual(visual_id: str, visual_type: str, section_name: str, columns: list,
                      x: float, y: float, width: float, height: float) -> dict:
    """Build a bar/line/pie chart visual.json dict."""
    category = columns[:1]
    values = columns[1:] if len(columns) > 1 else columns
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x, "y": y, "z": 0,
            "height": height, "width": width,
            "tabOrder": 0
        },
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": {
                    "Category": {"projections": [make_column_projection(c) for c in category]},
                    "Y": {"projections": [make_column_projection(c) for c in values]},
                }
            },
            "visualContainerObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{section_name}'"}}},
                        "fontSize": {"expr": {"Literal": {"Value": "12D"}}}
                    }
                }]
            },
            "drillFilterOtherVisuals": True
        }
    }


def make_slicer_visual(visual_id: str, label: str,
                       x: float, y: float,
                       width: float = 200, height: float = 60) -> dict:
    """Build a slicer visual.json dict for a filter field."""
    # Clean any remaining noise from the label
    field_name = re.sub(r"[\u200b\u200c\u200d\ufeff\*]+", "", label).strip()
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x, "y": y, "z": 1000,
            "height": height, "width": width,
            "tabOrder": 1000
        },
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [{
                            "field": {
                                "Column": {
                                    "Expression": {
                                        "SourceRef": {"Entity": "TODO_Table"}
                                    },
                                    "Property": field_name
                                }
                            },
                            "queryRef": f"TODO_Table.{field_name}",
                            "active": True
                        }]
                    }
                }
            },
            "objects": {
                "data": [{
                    "properties": {
                        "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}
                    }
                }],
                "header": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}}
                    }
                }]
            },
            "drillFilterOtherVisuals": True
        }
    }


def make_title_textbox(visual_id: str, title: str,
                       x: float = 20, y: float = 5,
                       width: float = 900, height: float = 45) -> dict:
    """Build a title textbox visual."""
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x, "y": y, "z": 2000,
            "height": height, "width": width,
            "tabOrder": 2000
        },
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [{
                    "properties": {
                        "paragraphs": [{
                            "textRuns": [{
                                "value": title,
                                "textStyle": {
                                    "fontWeight": "bold",
                                    "fontSize": "18pt"
                                }
                            }],
                            "horizontalTextAlignment": "left"
                        }]
                    }
                }]
            },
            "drillFilterOtherVisuals": True
        }
    }


def build_page_visuals(page_index: int, section_name: str, section_data: dict,
                       filters: list, report_name: str) -> list:
    """
    Build the list of visual dicts for a single page.
    Returns list of visual dicts (each will be written to its own visual.json file).
    """
    visuals = []
    columns = section_data.get("columns", [])
    current_y = 130.0  # Start below slicers row

    # Page 1: add slicers for global filters
    if page_index == 0 and filters:
        slicer_x = 20.0
        slicer_y = 60.0
        for flt in filters:
            label = flt.get("label") or ""
            if not label:
                # Extract label from raw text: take text before first
                # filter-type keyword or asterisk
                raw = flt.get("raw", "")
                # Strip zero-width spaces
                raw = re.sub(r"[\u200b\u200c\u200d\ufeff]+", "", raw)
                m = re.match(r"^([A-Za-z][^\*\n]+?)(?:\*?\s+(?:Global|Page|Local)|$)", raw)
                label = m.group(1).strip() if m else raw.split("*")[0].strip()
            # Strip trailing asterisk and zero-width spaces
            label = re.sub(r"[\u200b\u200c\u200d\ufeff\*]+$", "", label).strip()
            if label:
                vid = _visual_id()
                visuals.append(make_slicer_visual(vid, label, slicer_x, slicer_y))
                slicer_x += 220.0

    # Title textbox
    title_id = _visual_id()
    page_title = re.sub(r"^Page \d+,?\s*", "", section_name).strip() or section_name
    visuals.append(make_title_textbox(title_id, page_title))

    # Main data visual
    if columns:
        visual_type = infer_visual_type(section_name, columns)
        vid = _visual_id()
        if visual_type == "tableEx":
            visuals.append(make_table_visual(
                vid, section_name, columns,
                x=20, y=current_y, width=1240, height=570
            ))
        else:
            visuals.append(make_chart_visual(
                vid, visual_type, section_name, columns,
                x=20, y=current_y, width=1240, height=540
            ))

    return visuals


def generate_pbip(report: dict, output_dir: str) -> str:
    """
    Generate the complete .pbip folder structure for a single visual report.
    Returns path to the generated .Report folder.
    """
    out = Path(output_dir)
    report_name = report["name"]
    safe_rpt = re.sub(r"[^\w\s\-]", "", report_name).strip().replace(" ", "_")
    folder_name = re.sub(r"\W+", "_", report.get("target_folder") or report["folder"])

    # Root: output/pbip/{folder}/{safe_rpt}.Report/
    report_dir = out / folder_name / f"{safe_rpt}.Report"
    def_dir = report_dir / "definition"
    pages_dir = def_dir / "pages"
    report_dir.mkdir(parents=True, exist_ok=True)
    def_dir.mkdir(exist_ok=True)
    pages_dir.mkdir(exist_ok=True)

    layout = report.get("layout", {})
    filters = report.get("filters", [])

    # --- definition.pbir (semantic model binding) ---
    # Uses byPath to reference the .SemanticModel folder in the same Fabric workspace
    # Developer updates this path to the correct model
    semantic_model_name = _infer_semantic_model(report)
    pbir = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{semantic_model_name}.SemanticModel"
            }
        }
    }
    (report_dir / "definition.pbir").write_text(
        json.dumps(pbir, indent=2), encoding="utf-8"
    )

    # --- definition/report.json (report-level metadata, NO pages/visuals) ---
    c = _get_cfg()
    theme_name = c.theme_name if c else "CY22SU08"
    report_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": theme_name,
                "reportVersionAtImport": {
                    "visual": "1.8.71",
                    "report": "2.0.71",
                    "page": "1.3.71"
                },
                "type": "SharedResources"
            }
        },
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True
        },
        "slowDataSourceSettings": {
            "isCrossHighlightingDisabled": False,
            "isSlicerSelectionsButtonEnabled": False,
            "isFilterSelectionsButtonEnabled": False,
            "isFieldWellButtonEnabled": False,
            "isApplyAllButtonEnabled": False
        }
    }
    (def_dir / "report.json").write_text(
        json.dumps(report_json, indent=2), encoding="utf-8"
    )

    # --- definition/version.json ---
    version_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"
    }
    (def_dir / "version.json").write_text(
        json.dumps(version_json, indent=2), encoding="utf-8"
    )

    # --- Pages ---
    page_sections = list(layout.items()) if layout else [("main", {"columns": [], "raw": ""})]
    page_names = []

    for page_idx, (section_name, section_data) in enumerate(page_sections):
        sec_id = _page_name(page_idx)
        page_display = re.sub(r"^(?:Tab|Page|Table)\s*\d+[,\s]*", "", section_name).strip()
        if not page_display:
            page_display = section_name

        page_dir = pages_dir / sec_id
        visuals_dir = page_dir / "visuals"
        page_dir.mkdir(exist_ok=True)
        visuals_dir.mkdir(exist_ok=True)
        page_names.append(sec_id)

        # page.json
        page_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
            "name": sec_id,
            "displayName": page_display[:50],
            "displayOption": "FitToPage",
            "height": c.canvas_height if c else 720,
            "width": c.canvas_width if c else 1280
        }
        (page_dir / "page.json").write_text(
            json.dumps(page_json, indent=2), encoding="utf-8"
        )

        # Visuals — each gets its own folder + visual.json
        visuals = build_page_visuals(
            page_idx, section_name, section_data, filters, report_name
        )
        for visual_dict in visuals:
            vid = visual_dict["name"]
            vis_dir = visuals_dir / vid
            vis_dir.mkdir(exist_ok=True)
            (vis_dir / "visual.json").write_text(
                json.dumps(visual_dict, indent=2), encoding="utf-8"
            )

    # --- pages/pages.json ---
    pages_meta = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": page_names,
        "activePageName": page_names[0] if page_names else "ReportSection1"
    }
    (pages_dir / "pages.json").write_text(
        json.dumps(pages_meta, indent=2), encoding="utf-8"
    )

    # --- .pbip project file (one level up from .Report folder) ---
    pbip_content = {
        "version": "1.0",
        "artifacts": [
            {"report": {"path": f"{safe_rpt}.Report"}}
        ],
        "settings": {"enableTmdlV2": True}
    }
    pbip_file = out / folder_name / f"{safe_rpt}.pbip"
    pbip_file.write_text(json.dumps(pbip_content, indent=2), encoding="utf-8")

    # --- README.md ---
    _write_readme(report_dir, report, section_name=section_name,
                  semantic_model_name=semantic_model_name)

    return str(report_dir)


def _infer_semantic_model(report: dict) -> str:
    """Return the best-matching semantic model name for *report*.

    Checks ``report['_spec_model']`` first (set by spec_parser when the spec
    confirms the model explicitly), then delegates to cfg.infer_semantic_model()
    which reads [model_keywords] from pbi.properties.
    """
    if report.get("_spec_model"):
        return report["_spec_model"]
    c = _get_cfg()
    if c is not None:
        return c.infer_semantic_model(report)
    return "TODO_SemanticModel"


def _write_readme(report_dir: Path, report: dict,
                  section_name: str, semantic_model_name: str):
    """Write a README.md with full requirements and developer TODO checklist."""
    lines = [
        f"# {report['name']}",
        "",
        f"**Folder:** {report.get('folder', '')} / {report.get('target_folder', '')}",
        f"**Format:** Visual (.pbip)",
        f"**Suggested Semantic Model:** `{semantic_model_name}.SemanticModel`",
        f"**Legacy Report(s):** {report.get('legacy_reports', 'N/A')}",
        f"**Legacy Users:** {report.get('legacy_users', 'N/A')}",
        "",
        "## Summary",
        report.get("summary", ""),
        "",
        "## Developer TODO",
        "",
        "### 1. Connect Semantic Model",
        "Edit `definition.pbir`:",
        f"- Verify `byPath` points to the correct `.SemanticModel` folder",
        f"- If the model is in a different workspace, switch to `byConnection` and set the GUID",
        "",
        "### 2. Map Table & Column Names",
        "In each `visuals/{id}/visual.json`, replace:",
        "- `TODO_Table` → actual table/entity name from the semantic model",
        "- Column `Property` values → exact column names from the model",
        "",
        "### 3. Slicer Configuration",
        "Review slicer visuals and set appropriate filter mode (Between/Dropdown/List).",
        "",
    ]

    if report.get("filters"):
        lines += ["## Filters"]
        for flt in report["filters"]:
            if "label" in flt:
                req_marker = "*" if flt.get("required") else ""
                lines.append(
                    f"- **{flt['label']}{req_marker}** "
                    f"| {flt.get('filter_type','?')} "
                    f"| {flt.get('select','?')} select"
                    f"{' — ' + flt['notes'] if flt.get('notes') else ''}"
                )
            else:
                lines.append(f"- {flt.get('raw', str(flt))}")
        lines.append("")

    if report.get("parameters"):
        lines += ["## Parameters"]
        for p in report["parameters"]:
            if "label" in p:
                req_marker = " *(required)*" if p.get("required") else ""
                lines.append(f"- **{p['label']}**{req_marker} | {p.get('select','?')} select")
            else:
                lines.append(f"- {p.get('raw', str(p))}")
        lines.append("")

    if report.get("requirements"):
        lines += ["## Requirements"]
        for req in report["requirements"]:
            rid = req.get("id") or ""
            lines.append(f"- **{rid}**: {req.get('text', '')}")
        lines.append("")

    if report.get("layout"):
        lines += ["## Layout (Pages)"]
        for sec, data in report["layout"].items():
            cols = data.get("columns", [])
            lines.append(f"### {sec}")
            for c in cols:
                lines.append(f"  - {c}")
        lines.append("")

    (report_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def generate_all_pbip(parsed_frd: dict, output_dir: str) -> list:
    """Generate .pbip folders for all visual reports in the parsed FRD."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []
    for report in parsed_frd["reports"]:
        if report["report_format"] != "Visual":
            continue
        path = generate_pbip(report, output_dir)
        generated.append(path)
    return generated


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate .pbip folders from parsed FRD JSON")
    ap.add_argument("frd_json", help="Parsed FRD JSON file (output of frd_parser.py)")
    ap.add_argument("-o", "--output", default="output/pbip")
    ap.add_argument("--report", help="Filter to a specific report name (partial match)")
    args = ap.parse_args()

    with open(args.frd_json, encoding="utf-8") as f:
        frd = json.load(f)

    if args.report:
        frd["reports"] = [r for r in frd["reports"] if args.report.lower() in r["name"].lower()]

    files = generate_all_pbip(frd, args.output)
    print(f"Generated {len(files)} .pbip report folders → {args.output}")
    for f in files:
        print(f"  {f}")
