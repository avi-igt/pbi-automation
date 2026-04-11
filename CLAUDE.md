# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Goal

Automate development of Power BI reports and dashboards from a functional requirements document (FRD) using AI. The FRD is:
```
MO - Performance Wizard Ad Hoc Reporting FRD v1.0.docx
```

## Pipeline Architecture

Four Python scripts form the full pipeline:

| Script | Role |
|---|---|
| `frd_parser.py` | Parses the `.docx` FRD using `python-docx` + `lxml`, extracting SDT content controls (Azure DevOps work items embedded in Word). Outputs structured JSON per report. |
| `rdl_generator.py` | Generates `.rdl` XML (Report Definition Language) for paginated reports from parsed JSON. |
| `pbip_generator.py` | Generates `.pbip` folder structures for visual reports from parsed JSON. |
| `generate_all.py` | Orchestrates the full pipeline: parse → RDL → PBIP. |

Run the full pipeline:
```bash
python generate_all.py
```

Run the parser alone:
```bash
python run_parser.py
```

**Reference implementation** from OpenClaw bot (take inspiration, improve upon):
`/Users/aps/.openclaw/workspace/powerbi-frd-automation/`

## Output Structure

```
output/
  json/frd_parsed.json     ← all ~95 reports as structured JSON
  rdl/                     ← .rdl files organized by folder (per FRD folder field)
  pbip/                    ← .pbip report folders organized by folder
```

## Report Types & Templates

### Paginated Reports (.rdl)

Two data source patterns:
1. **Semantic model** — uses `MO_*.pbip` datasets as data source. Template: `/Users/aps/git/lpc-v1-app-ldi-pbi/MO_Report_Template.PaginatedReport/MO_Report_Template.rdl`
2. **Direct ODBC/DB2** — connects to BOADB (DB2 database). Example: `/Users/aps/git/lpc-v1-app-ldi-pbi/1042 Tax Report.PaginatedReport/`

RDL namespace: `http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition`

### Visual Reports (.pbip)

Two data source patterns:
1. **Semantic model** — binds to `MO_*.SemanticModel` via `definition.pbir` `byPath` reference. Example: `/Users/aps/git/lpc-v1-app-ldi-pbi/Activated Packs.Report/`
2. **ODBC/Snowflake** — direct connection. Example: `/Users/aps/git/lpc-v1-app-ldi-pbi/TMIR Retailer.rdl`

### `.pbip` folder structure
```
ReportName.Report/
  definition.pbir          ← binds to semantic model via byPath: "../ModelName.SemanticModel"
  definition/
    report.json            ← visual layout, pages, visuals
    pages/
    version.json
  StaticResources/
```

## Semantic Models

Available MO datasets in `/Users/aps/git/lpc-v1-app-ldi-pbi/`:
`MO_CoreTables`, `MO_DrawData`, `MO_IntervalSales`, `MO_Inventory`, `MO_Invoice`, `MO_LVMSales`, `MO_LVMTransactional`, `MO_Payments`, `MO_Promotions`, `MO_Sales`, `MO_WinnerData`

Most reports should bind to one of these. The `definition.pbir` `byPath` field should reference the `.SemanticModel` folder relative to the report folder.

## FRD Parsing Notes

- The FRD uses **Azure DevOps SDT content controls** embedded in Word — use `lxml` to parse `w:sdt` elements, not plain paragraph text.
- Work item headers follow pattern: `MO-XXXXX,Draft,Functional/Business - ` — strip this noise.
- Each report has fields: Report Title, Legacy Report(s), Legacy Users, Summary, Report Format, Sort, New Folder, Folder, Notes.
- `Report Format` determines paginated vs visual: look for "paginated"/"RDL" vs "Power BI"/"visual".

## Environment

- Platform: Microsoft Fabric + Power BI Premium capacity
- Python dependencies: `python-docx`, `lxml` (for FRD parsing)
- Output is for **manual review only** — do not auto-publish to Fabric/Power BI service
- If a report's requirements are better suited to paginated format, recommend that over visual
