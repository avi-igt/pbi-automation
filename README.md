<div align="center">

<img src="assets/banner.svg" alt="pbi-automation" width="860"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.9%2B-F2C811?style=flat-square&logo=python&logoColor=black)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-06d6a0?style=flat-square)](LICENSE)
[![Power BI](https://img.shields.io/badge/Power%20BI-Fabric-F2C811?style=flat-square&logo=powerbi&logoColor=black)](https://app.powerbi.com)
[![Reports](https://img.shields.io/badge/Reports-auto%20generated-3b82f6?style=flat-square)](#output-file-formats)
[![FRD Format](https://img.shields.io/badge/FRD-ADO%20%2F%20Word-8b5cf6?style=flat-square)](#frd-format-requirements)

**Turn a Functional Requirements Document into Power BI report files in seconds — not days.**

[Quick Start](#quick-start) · [Pipeline](#pipeline) · [Configuration](#configuration) · [Data Sources](#data-sources) · [Spec-to-Report](#spec-to-report-path) · [After Generation](#after-generation) · [Full Lifecycle](#full-development-lifecycle) · [Output Formats](#output-file-formats) · [Extending](#extending-the-tool) · [Troubleshooting](#troubleshooting)

</div>

---

## Why pbi-automation?

A typical FRD describes Power BI reports with attributes: layouts, parameters, filters, requirements. Translating each one manually into `.rdl` XML or `.pbip` JSON takes developers hours per report.

**pbi-automation parses the FRD once and generates all report scaffolding automatically** — correct RDL structure, proper semantic model bindings, page-per-section PBIP layouts, and human-readable review specs. Developers start from a working skeleton instead of a blank canvas.

Everything deployment-specific lives in **`pbi.properties`** — workspace name, tenant ID, dataset GUIDs, ODBC DSN names, brand colours, fonts, and keyword rules. To deploy for a different state or environment: edit `pbi.properties` only, no code changes required.

---

## Pipeline

<div align="center">
<img src="assets/pipeline.svg" alt="FRD → Parse → JSON checkpoint → RDL / PBIP / .md" width="1060"/>
</div>

### Path A — FRD → JSON → Reports (full pipeline)

| Step | Script | Input | Output | Notes |
|------|--------|-------|--------|-------|
| 1 | `frd_parser.py` | FRD `.docx` | `output/json/frd_parsed.json` | **Human checkpoint** — review and edit before generating |
| 2 | `rdl_generator.py` | `frd_parsed.json` | `output/rdl/**/*.rdl` | Paginated reports with header, footer, logo, params |
| 3 | `pbip_generator.py` | `frd_parsed.json` | `output/pbip/**/` | Visual report folders with pages and visuals |
| 4 | `spec_generator.py` | FRD `.docx` | `output/specs/*.md` | Human-readable review docs; datasource details confirmed |

**The JSON is the checkpoint.** After Step 1, open `output/json/frd_parsed.json`, verify field names, fix any incorrect `report_format` or `datasource_type` values, then run Steps 2–4. All generators read from JSON — there is no lossy intermediate format.

### Path B — Reviewed Spec → Reports (second-pass generation)

Once a developer has reviewed and confirmed a spec `.md` (filling in the correct semantic model, SQL query, connection string, etc.), the spec itself becomes a generator input — **no FRD or JSON required**.

| Script | Input | Output | Notes |
|--------|-------|--------|-------|
| `spec_to_rdl.py` | `output/specs/*.md` | `output/from-spec/rdl/` | Paginated reports from reviewed specs |
| `spec_to_pbip.py` | `output/specs/*.md` | `output/from-spec/pbip/` | Visual reports from reviewed specs |

Internally, both scripts use **`spec_parser.py`** to translate the `.md` format into the same report dict used by `rdl_generator.py` and `pbip_generator.py`. Any values confirmed in the spec (connection string, model name, SQL query) take precedence over auto-inferred values.

---

## Prerequisites

- **Python 3.9+**
- **pip**
- Your FRD as a `.docx` file (ADO / Performance Wizard format)

### Windows

Fully supported. Run in **Windows Terminal** or **PowerShell** for correct Unicode rendering. CLI colours are automatically disabled on Windows — output is plain text but fully functional.

---

## Quick Start

**1. Clone and install**

```bash
git clone https://github.com/avi-igt/pbi-automation.git
cd pbi-automation
pip install -r requirements.txt
```

**2. Configure**

Edit `pbi.properties` with your Fabric workspace name, tenant ID, and dataset GUIDs (find GUIDs in the Fabric workspace URL or Power BI Report Builder connection dialog).

**3. Add your FRD**

Copy your FRD `.docx` into the repo root:

```
pbi-automation/
  Your FRD v1.0.docx     ← place it here
  generate_all.py
  pbi.properties
  src/
```

**4. Run**

```bash
python generate_all.py "Your FRD v1.0.docx"
```

All report files land in `output/`.

---

## Usage

### Full pipeline

```bash
# Default — looks for the FRD path configured in pbi.properties
python generate_all.py

# Explicit FRD path
python generate_all.py "path/to/FRD.docx"

# Custom output directory
python generate_all.py "path/to/FRD.docx" -o ./my-output
```

### Run one step at a time

```bash
python generate_all.py --only parse   # Step 1: FRD → frd_parsed.json
python generate_all.py --only rdl     # Step 2: JSON → .rdl  (requires prior parse)
python generate_all.py --only pbip    # Step 3: JSON → .pbip (requires prior parse)
python generate_all.py --only spec    # Step 4: FRD → .md review docs
```

**Recommended workflow for large FRDs:**

```bash
# 1. Parse only — inspect the JSON before generating
python generate_all.py --only parse

# 2. Edit output/json/frd_parsed.json if needed
#    (fix report_format, datasource_type, rename columns, adjust folders, etc.)

# 3. Generate reports from the reviewed JSON
python generate_all.py --only rdl
python generate_all.py --only pbip
```

### Filter to a single report

```bash
python generate_all.py --report "Chain Store"
python generate_all.py --report "Keno" --only rdl
```

### Run modules directly

```bash
python -m src.frd_parser    "FRD.docx" -o output/json/frd_parsed.json
python -m src.rdl_generator  output/json/frd_parsed.json -o output/rdl
python -m src.pbip_generator output/json/frd_parsed.json -o output/pbip
python src/spec_generator.py "FRD.docx" --output-dir output/specs
```

### Generate from reviewed specs (Path B)

```bash
# All Paginated specs in output/specs/ → output/from-spec/rdl/
python src/spec_to_rdl.py output/specs/

# All Visual specs in output/specs/ → output/from-spec/pbip/
python src/spec_to_pbip.py output/specs/

# Single spec file
python src/spec_to_rdl.py output/specs/mo-wild-ball-sales-report.md

# Custom output directory
python src/spec_to_rdl.py output/specs/ -o output/custom/rdl

# Filter by report name (partial match, case-insensitive)
python src/spec_to_rdl.py output/specs/ --report "Wild Ball"
python src/spec_to_pbip.py output/specs/ --report "Cash Pop"
```

Each script automatically skips specs of the wrong format (e.g. `spec_to_rdl.py` silently skips Visual specs).

---

## Configuration

All deployment-specific settings live in **`pbi.properties`**. Edit this file before running.

### Fabric workspace

```ini
[fabric]
workspace_name  = Missouri - D1V1
tenant_id       = your-tenant-guid-here
```

### Dataset GUIDs

One line per semantic model. GUIDs are found in the Fabric workspace URL:  
`app.powerbi.com/groups/<workspace-id>/datasets/<dataset-guid>/...`

```ini
[datasets]
MO_Sales            = 45ddd7fc-a26e-4f4b-86c5-fac56b42553b
MO_DrawData         = dfff48d9-8c93-4875-ab98-d4ca8b20e24c
MO_WinnerData       = 96a3324d-ae40-47a6-bbd2-a83223f5a843
# ... one entry per semantic model used by reports
```

### Datasource type detection

Keywords matched **case-insensitively** against report name + summary + notes. First matching key wins. Reports not matching any keyword default to `semantic_model`.

```ini
[datasource_keywords]
snowflake = RDST, TMIR, Security
db2       = claims, payments, annuities, debt, setoff, player, ssn, claimant
```

### Semantic model selection

Keywords matched against report name + summary. First match wins. Put broader/catch-all models last.

```ini
[model_keywords]
MO_LVMTransactional = lvm transaction, lvm transactional
MO_Invoice          = brightstar invoice, brightstar
MO_DrawData         = draw game, jackpot, winning number, cash pop, keno, draw data
MO_WinnerData       = winner, prize, claimant
MO_Payments         = payment, check, annuity, 1042, tax report, claim
MO_Inventory        = inventory, pack, activated, aging, bin, scratchers
MO_IntervalSales    = interval, hourly, weekly
MO_LVMSales         = lvm, vending, vending machine
MO_CoreTables       = retailer list, chain store, district, device list, terminal list, terminal
MO_Promotions       = promotion, promo, cashless, device
MO_Sales            = sales, validations, cancels, retailer, wager, ticket, revenue
```

### ODBC data sources

```ini
[odbc]
db2_source_name     = BOADB            # DB2 / ARDB data source name
db2_dsn             = MOS-Q1-BOADB    # DB2 DSN

sfodbc_source_name  = LPC_E2_SFODBC   # Snowflake ODBC data source name
sfodbc_dsn          = MOS-PX-SFODBC   # Snowflake DSN
```

### RDL layout defaults

```ini
[rdl]
page_width      = 11in
page_height     = 8.5in
margin          = 0.2in
default_font    = Segoe UI
title_font      = Segoe UI Light
title_font_size = 14pt
timezone        = Central Standard Time
```

### PBIP canvas and branding

```ini
[pbip]
canvas_width        = 1280
canvas_height       = 720
theme_name          = CY22SU08
brand_color_grid    = #D6DBEA
brand_color_header  = #FAFAFA
```

### File paths

```ini
[paths]
rdl_template    = templates/MO_Report_Template.rdl   # logo source
frd_docx        = Your FRD v1.0.docx                 # default FRD path
sql_dir         = sql                                  # hand-authored SQL directory
```

---

## Data Sources

The tool detects one of three datasource types per report based on keywords in `pbi.properties`:

| Type | Connection | When used |
|---|---|---|
| `semantic_model` | Fabric PBIDATASET (DAX) | Default — most reports |
| `db2` | ODBC → DB2 / ARDB (`BOA_PS` schema) | Claims, payments, annuities, tax reports |
| `snowflake` | ODBC → Snowflake (`TXNDTL`, `DIMCORE` schemas) | TMIR, RDST, Security reports |

Detection is keyword-driven via `[datasource_keywords]` in `pbi.properties`. To add or change which reports use a particular datasource, edit the keyword lists — no code changes needed.

### Hand-authored SQL for ODBC reports

For `db2` and `snowflake` reports, the generator looks for a `.sql` file in the `sql/` directory. The file name must match the report name (spaces → underscores):

```
sql/
  1042_Tax.sql
  Debt_Offsets.sql
  TMIR_Retailer.sql
```

If a `.sql` file is found it is embedded verbatim in the generated `.rdl`. If not found, the generator produces an auto-stub with a comment indicating the expected filename. The stub is valid XML but requires a developer to write the real query.

The `sql/` directory is **not committed** — SQL files are maintained alongside the reports they belong to, outside the generator repo.

---

## Spec-to-Report Path

After running the full pipeline, `output/specs/` contains one `.md` file per report. These files are designed to be both human-readable **and** machine-parseable — a developer can review them, fill in any missing values, and then feed them directly back into the generators.

### What to confirm in a spec before regenerating

| Spec section | What to check / fill in |
|---|---|
| `## Data Source` | Confirm the semantic model name, or fill in DSN and source name for ODBC reports |
| `## Datasets` | Add or correct the SQL query (for ODBC reports) in the ` ```sql ``` ` block |
| `## Parameters` / `## Filters` | Verify labels, single/multiple selection, required flag |
| `## Layout` | Confirm column order and names |
| `## Metadata` | Check `Report Format` is `Paginated` or `Visual` |

### How confirmed values flow through

`spec_parser.py` reads the spec and injects confirmed values as `_spec_*` override keys:

| Spec field | Override key | Used by |
|---|---|---|
| Connection string (code block) | `_spec_connect_string` | `rdl_generator.py` |
| Semantic model name | `_spec_model` | `rdl_generator.py`, `pbip_generator.py` |
| Datasource name (`WorkspaceSlug_ModelName`) | `_spec_datasource_name` | `rdl_generator.py` |
| Dataset GUID | `_spec_guid` | `rdl_generator.py` |
| SQL query (` ```sql ``` ` block) | `_spec_sql` | `rdl_generator.py` |

These override keys take precedence over auto-inferred values, so a confirmed spec produces more accurate output than the first-pass FRD parse.

### Output location

Path B output lands in a separate directory to avoid overwriting Path A output:

```
output/
  rdl/              ← Path A: generated from frd_parsed.json
  pbip/             ← Path A: generated from frd_parsed.json
  from-spec/
    rdl/            ← Path B: generated from reviewed .md specs
    pbip/           ← Path B: generated from reviewed .md specs
```

---

## After Generation

### Paginated Reports (`.rdl`)

| Step | What to do |
|---|---|
| 1 | Open the `.rdl` in **Power BI Report Builder** |
| 2 | Verify `<ConnectString>` — auto-populated from `pbi.properties` dataset GUIDs |
| 3 | For semantic model reports: replace `TODO_Table[ColumnName]` stubs with real DAX field references |
| 4 | For ODBC reports: verify or replace the embedded SQL query |
| 5 | Validate layout and publish to Fabric |

### Visual Reports (`.pbip`)

| Step | What to do |
|---|---|
| 1 | Read the per-report `README.md` in the `.pbip` folder — it contains the requirements checklist |
| 2 | Verify `definition.pbir` → `byPath` points to the correct `.SemanticModel` folder |
| 3 | In each `visual.json`, replace `TODO_Table` with the actual entity name from your semantic model |
| 4 | Open the `.pbip` in **Power BI Desktop (Fabric mode)** and validate |

### Review Docs (`.md` specs)

The `output/specs/` folder contains one `.md` file per report with extracted metadata, parameters, layout columns, business rules, and the inferred data source (type, connection string, GUID, SQL path). These serve a dual purpose:

- **Documentation** — human-readable handoff artifacts for developer review meetings
- **Generator input** — after review and confirmation, feed directly to `spec_to_rdl.py` or `spec_to_pbip.py` for Path B generation (see [Spec-to-Report Path](#spec-to-report-path))

> **Tip:** Use `--report "Name"` to generate and test one report at a time before running the full pipeline.

---

## Full Development Lifecycle

pbi-automation handles the first mile — turning requirements into report scaffolding. Two companion open-source tools cover the rest of the lifecycle. Each tool is independent; install only what you need.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 · SCAFFOLD          pbi-automation  (this tool)  · Python · MIT   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FRD.docx  ──►  frd_parser  ──►  frd_parsed.json  ──►  .rdl / .pbip / .md │
│                                                                             │
│  Reviewed .md spec  ──────────────────────────────►  .rdl / .pbip          │
│                                                                             │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │  generated .rdl and .pbip files on disk
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 · DEVELOP           pbi-cli           (optional)  · Python · MIT  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  • Connect to running Power BI Desktop (TOM / ADOMD.NET via pythonnet)     │
│  • List tables, columns, measures  →  fill in TODO stubs in generated files│
│  • Execute and validate DAX queries before embedding in .rdl                │
│  • Add / update visuals, filters, themes in PBIR JSON files                 │
│  • AI-assisted iteration via Claude Code skills                             │
│                                                                             │
│  Install:  pip install pbi-cli-tool                                         │
│  Repo:     https://github.com/MinaSaad1/pbi-cli                             │
│                                                                             │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │  developer-validated report files
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3 · SHIP              pbi-tools         (optional)  · C# · AGPL-3.0 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  • extract:  PBIX → PbixProj folder  (git-friendly source control)         │
│  • compile:  PbixProj folder → PBIX  (ready to publish)                    │
│  • deploy:   Push reports + datasets to Power BI Service via REST + XMLA   │
│              - Multi-environment manifests  (dev / UAT / prod)              │
│              - Dataset refresh automation  (full / incremental / partition) │
│              - Gateway binding + credential injection                       │
│              - Service Principal auth for CI/CD pipelines                   │
│                                                                             │
│  Install:  https://pbi.tools  (Windows exe or .NET Core cross-platform)    │
│  Repo:     https://github.com/pbi-tools/pbi-tools                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Typical end-to-end workflow

```bash
# ── PHASE 1: Generate scaffolding ─────────────────────────────────────────
python generate_all.py "MO FRD v1.0.docx"
# → output/rdl/**/*.rdl   (paginated reports)
# → output/pbip/**/       (visual reports)
# → output/specs/*.md     (review docs)

# Review specs, confirm datasource / SQL / model name, then regenerate
python src/spec_to_rdl.py output/specs/  -o output/from-spec/rdl
python src/spec_to_pbip.py output/specs/ -o output/from-spec/pbip

# ── PHASE 2: Develop & validate (pbi-cli) ─────────────────────────────────
pbi connect localhost:50000          # connect to running PBI Desktop
pbi table list                       # discover real table / column names
pbi dax execute "EVALUATE Sales"     # validate DAX before embedding in .rdl
pbi visual list output/pbip/Reports_Sales/Cash_Pop_Performance.Report/

# ── PHASE 3: Source control + deploy (pbi-tools) ──────────────────────────
pbi-tools extract --input MyReport.pbix --project-folder src/MyReport
git add . && git commit -m "feat: add Cash Pop scaffold"

pbi-tools deploy --manifest deploy/manifest.json \
                 --environment prod \
                 --workspace "Missouri - D1V1"
```

### Tool comparison

| | pbi-automation | pbi-cli | pbi-tools |
|---|---|---|---|
| **Phase** | Requirements → scaffold | Development iteration | Source control + deploy |
| **Language** | Python | Python | C# / .NET |
| **PBI Desktop needed** | No | Yes (for TOM features) | Yes (Desktop edition) or No (Core edition) |
| **Power BI Service needed** | No | No | Yes (for deploy) |
| **Works offline** | Yes | Partial | Partial |
| **License** | MIT | MIT | AGPL-3.0 |
| **AI integration** | Claude Code | Claude Code (built-in skills) | None |

> **AGPL note:** pbi-tools is licensed under AGPL-3.0. For internal enterprise use this is fine. The copyleft clause only applies if you distribute pbi-tools as part of software shipped to external customers.

---

## Output File Formats

### Paginated Reports — `.rdl`

```
output/rdl/
  Reports_Brightstar/
    Active_Keno_Retailers_Report.rdl
    Brightstar_Invoice_Report.rdl
    1042_Tax.rdl
    ...
  Reports_Lottery_Sales/
    Daily_Sales_Summary.rdl
    ...
```

Each generated `.rdl` includes:

| Element | What's generated |
|---|---|
| XML schema | Correct 2016 RDL with `<ReportSections>` wrapper + all namespaces |
| Data source | `PBIDATASET` (semantic model) or `ODBC` (DB2 / Snowflake) — wired from `pbi.properties` |
| Dataset query | DAX `EVALUATE SUMMARIZECOLUMNS(...)` stub or hand-authored / auto-generated SQL |
| ConnectString | Auto-populated from `pbi.properties` GUIDs and DSN names |
| Parameters | `<ReportParameter>` + `<QueryParameter>` linkage |
| Tablix | Header row + data row for every layout column |
| Page header | Report name + logo + run date/time |
| Page footer | Report name + page X of Y |
| Comments | All FRD requirement IDs embedded as XML comments; `sql_source: file/stub` annotation |

### Visual Reports — `.pbip`

```
output/pbip/
  Reports_Brightstar/
    Cash_Pop_Performance.pbip
    Cash_Pop_Performance.Report/
      definition.pbir          ← semantic model binding
      definition/
        report.json            ← theme & settings
        version.json
        pages/
          pages.json           ← page order
          ReportSection1/      ← one per FRD layout section
            page.json
            visuals/
              {id}/visual.json ← title, slicers, data visual
      README.md                ← developer TODO checklist
```

Each generated `.pbip` includes:

| Element | What's generated |
|---|---|
| `definition.pbir` | `byPath` binding to the best-matched `MO_*.SemanticModel` (from `pbi.properties`) |
| Pages | One page per layout section from the FRD |
| Visual type | Inferred from section/column names: table, bar, line, pie, or card |
| Slicers | One slicer per filter defined in the FRD |
| Title textbox | Auto-populated from the section display name |
| `README.md` | Full requirements list + step-by-step checklist per report |

### Review Docs — `.md`

```
output/specs/
  1042-tax.md
  chain-store-list-report.md
  daily-sales-summary-by-terminal-report.md
  ...
```

One file per report containing: title, format, folder, legacy path, data source (type + connection details + SQL path), parameters/filters table, layout columns with inferred types and formats, and all business rule requirements.

---

## Project Structure

```
pbi-automation/
  generate_all.py          ← pipeline entry point (run this)
  pbi.properties           ← all deployment config: workspace, GUIDs, DSNs, keywords, fonts
  requirements.txt
  assets/
    banner.svg
    pipeline.svg
  src/
    config.py              ← reads pbi.properties; exposes cfg singleton used by all generators
    frd_parser.py          ← .docx → structured JSON (datasource_type inferred via pbi.properties)
    spec_generator.py      ← .docx → .md review docs (standalone or via pipeline)
    rdl_generator.py       ← JSON → .rdl XML (paginated reports)
    pbip_generator.py      ← JSON → .pbip folder (visual reports)
    spec_parser.py         ← .md spec → report dict (shared by spec_to_rdl + spec_to_pbip)
    spec_to_rdl.py         ← reviewed .md spec → .rdl (Path B, paginated)
    spec_to_pbip.py        ← reviewed .md spec → .pbip (Path B, visual)
  sql/                     ← hand-authored SQL files for ODBC reports (not committed)
    1042_Tax.sql           ← example: name matches report name with spaces→underscores
  templates/
    MO_Report_Template.rdl ← source of embedded logo (base64 extracted at runtime)
    specs/
      paginated-report-spec-template.md
      paginated-report-ODBC-spec-template.md
      paginated-report-snowflake-odbc-spec-template.md
      visual-report-spec-template.md
  output/                  ← generated files (not committed)
    json/frd_parsed.json   ← ★ human checkpoint — edit before re-running generators
    rdl/                   ← Path A: .rdl files from frd_parsed.json
    pbip/                  ← Path A: .pbip folders from frd_parsed.json
    specs/                 ← .md review docs (input for Path B after review)
    from-spec/
      rdl/                 ← Path B: .rdl files from reviewed .md specs
      pbip/                ← Path B: .pbip folders from reviewed .md specs
```

---

## FRD Format Requirements

This tool is designed for FRDs in the **Performance Wizard / Azure DevOps** format:

- Reports are **Heading 2** sections under folder **Heading 1** sections
- Each section contains **ADO SDT content controls** (Work Item type) with sub-sections:

| Sub-section | Content |
|---|---|
| `Summary` | Report title, format (Paginated/Visual), folder, legacy info |
| `Parameters` | Label · Single/Multiple · Notes |
| `Filters` | Label · Type (Global/Page/Local) · Context · Single/Multiple |
| `Layout` | Column names, optionally split by `<Tab N>`, `<Page N>`, `<Table N>` markers |
| `Requirements` | ADO work item IDs + requirement text |

Reports with `Report Format` = `Paginated` / `.rdl` → generate `.rdl`  
Reports with `Report Format` = `Visual` / `Power BI` / `.pbip` → generate `.pbip`

---

## Extending the Tool

### Add or change a semantic model

Edit `[datasets]` and `[model_keywords]` in `pbi.properties`. No code changes required.  
Place more-specific models before broader ones; the last entry is the catch-all default.

### Add or change a datasource type

Edit `[datasource_keywords]` in `pbi.properties`. No code changes required.  
More-specific keyword sets should be listed before broader ones.

### Add a new ODBC data source variant

Edit `src/rdl_generator.py` → `generate_rdl()`: add a branch alongside the `db2` / `snowflake` cases with the correct `<DataProvider>` and `<ConnectString>`. Add the corresponding DSN config to `[odbc]` in `pbi.properties`.

### Support a new FRD field

Edit `src/frd_parser.py` → `parse_summary()`: add the new field name to the `fields` list.

### Add a new visual type

Edit `src/pbip_generator.py`:
1. Add keywords to `_CHART_HINTS`
2. Add a `make_*_visual()` function following the same pattern
3. Call it from `build_page_visuals()`

### Deploy for a different state

1. Copy `pbi.properties` and update: `workspace_name`, `tenant_id`, all `[datasets]` GUIDs, `[odbc]` DSN names, `[datasource_keywords]` and `[model_keywords]` keyword lists
2. Replace `templates/MO_Report_Template.rdl` with the new state's template (for logo extraction)
3. Run the pipeline — no Python changes needed

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'docx'`**  
The package name is `python-docx`, not `docx`: `pip install python-docx`

**Reports show `"report_format": "Unknown"` in JSON**  
The `Report Format` field in the FRD summary is blank or non-standard. Find the entry in `output/json/frd_parsed.json` and set it to `"Paginated"` or `"Visual"`, then re-run `--only rdl` or `--only pbip`.

**Wrong datasource type detected (e.g. report classified as `snowflake` when it should be `semantic_model`)**  
Check `[datasource_keywords]` in `pbi.properties`. The matched keyword may be appearing in an unrelated part of the report name or summary. Remove overly broad keywords or tighten the phrases. The detection only searches report name + summary + notes (not legacy path).

**Wrong semantic model selected**  
Update `[model_keywords]` in `pbi.properties` — add a more specific keyword for the report to the correct model, or move that model higher in the list. As a quick fix, edit `definition.pbir` (visual) or the `<ConnectString>` (paginated) in the generated output.

**ODBC report has an auto-stub SQL query instead of the real SQL**  
Place a `.sql` file in the `sql/` directory named after the report (spaces → underscores, e.g. `Debt_Offsets.sql`) and re-run `--only rdl`. The generator will embed it automatically.

**Columns appear as one long string**  
Word has no spaces between column names. The parser splits on camelCase boundaries. For all-uppercase column names, inspect the `raw` field in `frd_parsed.json` and adjust `_split_columns()` in `frd_parser.py`.

**RDL opens with XML error in Report Builder**  
Run `python -c "import xml.etree.ElementTree as ET; ET.parse('output/rdl/path/to/file.rdl')"` to pinpoint the bad line, then check for unescaped `<`, `>`, `&`, or `--` in the report name, summary, or requirements fields in the JSON.

**`spec_to_rdl.py` raises `ValueError: report_format is 'Visual'`**  
The spec describes a Visual report. Use `spec_to_pbip.py` instead, or check that `Report Format` in the spec's `## Metadata` section says `Paginated`.

**Spec-generated `.rdl` has `TODO_SemanticModel` in the connection string**  
The `## Data Source` section of the spec is missing the confirmed semantic model name. Either fill in the `- **Semantic model:** \`ModelName.SemanticModel\`` line in the spec and re-run, or ensure the model name appears in `[model_keywords]` in `pbi.properties` for auto-inference.

**Spec-generated ODBC report has an auto-stub SQL instead of the real query**  
Add a ` ```sql ``` ` block under `## Datasets` in the spec `.md` file and re-run `spec_to_rdl.py`. The spec SQL takes priority over any `sql/` file.

---

<div align="center">

Built by the **Brightstar Lottery** Performance Wizard team.

[![GitHub](https://img.shields.io/badge/GitHub-avi--igt%2Fpbi--automation-181717?style=flat-square&logo=github)](https://github.com/avi-igt/pbi-automation)
[![MIT License](https://img.shields.io/badge/License-MIT-06d6a0?style=flat-square)](LICENSE)

</div>
