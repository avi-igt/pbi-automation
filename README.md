<div align="center">

<img src="assets/banner.svg" alt="pbi-automation" width="860"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.9%2B-F2C811?style=flat-square&logo=python&logoColor=black)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-06d6a0?style=flat-square)](LICENSE)
[![Power BI](https://img.shields.io/badge/Power%20BI-Fabric-F2C811?style=flat-square&logo=powerbi&logoColor=black)](https://app.powerbi.com)
[![Snowflake](https://img.shields.io/badge/Snowflake-connected-29B5E8?style=flat-square&logo=snowflake&logoColor=white)](https://www.snowflake.com/)

**Two Power BI automation tools for Brightstar Lottery — one repo.**

[Quick Start](#quick-start) · [Pipeline](#pipeline) · [report-generator](#report-generator) · [model-generator](#model-generator) · [Repository Structure](#repository-structure) · [Troubleshooting](#troubleshooting)

</div>

---

## What's in this repo

| Tool | Entry point | What it does |
|---|---|---|
| **report-generator** | `generate_reports.py` | FRD `.docx` → `.rdl` paginated reports + `.pbip` visual reports + `.md` spec docs |
| **model-generator** | `generate_models.py` | `semantic.properties` → `.SemanticModel` + `.Report` folder pairs (TMDL, Snowflake-backed) |

Both tools share a single repo, a single `requirements.txt`, and common `templates/` + `output/` directories. They are otherwise independent — each has its own config file and entry point.

---

## Quick Start

```bash
git clone https://github.com/avi-igt/pbi-automation.git
cd pbi-automation
pip install -r requirements.txt
```

### report-generator

```bash
# Run the full FRD → reports pipeline
python generate_reports.py "MO FRD v1.0.docx"
```

### model-generator

```bash
# List all configured models
python generate_models.py --list

# Generate all models (requires Snowflake credentials — see Authentication below)
export SNOWFLAKE_USER=your.name@ourlotto.com
python generate_models.py
```

---

## Pipeline

<div align="center">
<img src="assets/pipeline.svg" alt="pbi-automation pipeline — report-generator and model-generator" width="1060"/>
</div>

---

## report-generator

Turns a Functional Requirements Document (FRD `.docx`, Performance Wizard / ADO format) into ready-to-import Power BI report files. A single parse pass produces all report scaffolding — correct RDL structure, proper semantic model bindings, page-per-section PBIP layouts, and human-readable review specs.

### Running

```bash
python generate_reports.py                          # full pipeline (FRD → all outputs)
python generate_reports.py --only parse             # Step 1 only: FRD → JSON checkpoint
python generate_reports.py --only rdl               # Step 2 only: JSON → .rdl
python generate_reports.py --only pbip              # Step 3 only: JSON → .pbip
python generate_reports.py --only spec              # Step 4 only: FRD → .md review docs
python generate_reports.py --report "Tax"           # filter: generate only matching reports
```

### Two generation paths

**Path A — FRD → JSON → Reports (full pipeline)**

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `frd_parser.py` | FRD `.docx` | `output/json/frd_parsed.json` |
| 2 | `rdl_generator.py` | `frd_parsed.json` | `output/rdl/**/*.rdl` |
| 3 | `pbip_generator.py` | `frd_parsed.json` | `output/pbip/**/` |
| 4 | `spec_generator.py` | FRD `.docx` | `output/specs/*.md` |

The JSON is the **human checkpoint**. After Step 1, review and edit `output/json/frd_parsed.json` to fix any `report_format` or `datasource_type` values before running Steps 2–4.

**Path B — Reviewed Spec → Reports**

After a developer reviews and confirms a spec `.md`, feed it back directly — no FRD or JSON required:

```bash
python report_generator/spec_to_rdl.py output/specs/   # → output/from-spec/rdl/
python report_generator/spec_to_pbip.py output/specs/  # → output/from-spec/pbip/
```

### Configuration (`pbi.properties`)

All deployment-specific settings live here — edit before running.

```ini
workspace = Missouri - D1V1

[datasource_keywords]
# Keywords matched (case-insensitive) against report name + summary
# First match wins. Unmatched reports default to semantic_model.
snowflake = rdst, tmir, security, transaction
db2       = claims, payments, annuities, debt, setoff, player, ssn, claimant

[model_keywords]
# Keywords matched to select the correct semantic model binding
# More-specific entries first; last entry is the catch-all default
MO_Sales        = sales, validations, cancels
MO_DrawData     = draw, game
MO_CoreTables   = retailer list, chain store

[odbc]
db2_dsn     = MOS-Q1-BOADB
sfodbc_dsn  = MOS-PX-SFODBC

[snowflake_native]
host           = igtgloballottery-igtpxv1_ldi.privatelink.snowflakecomputing.com
implementation = 2.0
```

**Never hardcode** DSN names, workspace names, or dataset names. Everything reads from `pbi.properties` via `report_generator/config.py`.

### Data source detection

`config.py` auto-detects the data source per report by scanning name + summary + notes:

1. Match `[datasource_keywords] snowflake` → Snowflake ODBC
2. Match `[datasource_keywords] db2` → DB2 ODBC
3. Match `[model_keywords]` entries top-to-bottom → matching Semantic Model
4. Default: last model in `[model_keywords]`

### Hand-authored SQL

For ODBC reports, place a `.sql` file in `report_generator/sql/` named after the report (spaces → underscores). If found, it is embedded verbatim in the generated `.rdl`. If not found, the generator produces an auto-stub with a comment indicating the expected filename.

```
report_generator/sql/
  1042_Tax.sql
  TMIR_Retailer.sql
```

### Output

```
output/
  json/frd_parsed.json     ← human checkpoint — edit before re-running generators
  rdl/                     ← Path A: .rdl files (organized by FRD folder)
  pbip/                    ← Path A: .pbip report folders
  specs/                   ← .md review docs (also input for Path B)
  from-spec/
    rdl/                   ← Path B: .rdl from reviewed specs
    pbip/                  ← Path B: .pbip from reviewed specs
```

### After generation

**Paginated Reports (`.rdl`)**
1. Open in Power BI Report Builder
2. Verify `<ConnectString>` — auto-populated from `pbi.properties`
3. For semantic model reports: replace `TODO_Table[ColumnName]` stubs with real DAX field references
4. For ODBC reports: verify or replace the embedded SQL query
5. Validate and publish to Fabric

**Visual Reports (`.pbip`)**
1. Check `definition.pbir` → `byPath` points to the correct `.SemanticModel` folder
2. In each `visual.json`, replace `TODO_Table` with the actual entity name
3. Open in Power BI Desktop (Fabric mode) and validate

---

## model-generator

Turns a `semantic.properties` configuration file into Power BI semantic model artifacts by introspecting Snowflake table schemas. Generates a complete `.SemanticModel` (TMDL) + `.Report` (PBIR placeholder) folder pair ready to commit and deploy.

### Running

```bash
python generate_models.py                           # generate all configured models
python generate_models.py --model financial_daily   # generate one model only
python generate_models.py --list                    # list all configured models
python generate_models.py --env d1v1                # target environment (d1v1/c1v1/p1v1)
```

### Authentication

```bash
# SSO (recommended) — must run from PowerShell on Windows, not WSL
$env:SNOWFLAKE_USER = "your.name@ourlotto.com"
py generate_models.py

# Username + password
export SNOWFLAKE_USER=x
export SNOWFLAKE_PASSWORD=y
python generate_models.py
```

SSO (`authenticator = externalbrowser`) requires a native Windows Python session (browser callback fails in WSL). Use `$env:` in PowerShell.

### Configuration (`semantic.properties`)

```ini
[snowflake]
account       = igtgloballottery-igtpxv1_ldi
warehouse     = lpcdxv1_wh_ldi
database      = MOSQ1V1_DB_DH
role          = mosq1v1_ru_datareader
authenticator = externalbrowser          # SSO; use "snowflake" for user/pass

[snowflake.d1v1]
# Per-environment overrides — merged on top of [snowflake] when --env d1v1 is used
account = igtgloballottery-igtd2v1_ldi.privatelink   # .privatelink suffix required

[measure_suffixes]
# Columns ending in these suffixes get a hidden source column + CALCULATE(SUM(...)) measure
_COUNT    = int64,   0
_AMOUNT   = decimal, #,##0.00
_QUANTITY = int64,   #,##0

[dimensions]
# alias = SCHEMA.TABLE, primary_key=COLUMN, strategy=A|B
dates     = DIMCORE.DATES,     primary_key=DATE_KEY,     strategy=A
products  = DIMCORE.PRODUCTS,  primary_key=PRODUCT_KEY,  strategy=A
locations = DIMCORE.LOCATIONS, primary_key=LOCATION_KEY, strategy=B

[model.financial_daily]
display_name = Financial Daily LDI
fact_table   = FINANCIAL.FINANCIAL_DAILY
dimensions   = dates, products, locations
```

**Non-standard join key:** `dimensions = dates, products:GAME_PRODUCT_KEY`
→ produces `fromColumn: GAME_PRODUCT_KEY, toColumn: PRODUCT_KEY`

**Role-playing dimension:** add `inherit=<alias>` to reuse an existing dimension's YAML with a different alias.

### Star schema column rules

Applied automatically to every fact table column:

| Column | Output |
|---|---|
| Exact match on a dimension join key | Hidden, `int64` — relationship column only |
| Ends in `_COUNT` / `_AMOUNT` / `_QUANTITY` | Hidden source column + `CALCULATE(SUM(...))` DAX measure |
| Other `ALL_UPPERCASE` | Hidden |
| `Title Case` | Visible |

Suffix matching is configurable in `[measure_suffixes]` — add new types without any code changes.

### Output

```
output/models/
  Financial Daily LDI.SemanticModel/
    .platform
    definition.pbism
    definition/
      expressions.tmdl      ← Snowflake connection params (env-specific)
      relationships.tmdl    ← auto-generated from dimension config
      tables/
        FINANCIAL_DAILY.tmdl
        DATES.tmdl
        PRODUCTS.tmdl
        ...

  Financial Daily LDI.Report/
    .platform
    definition.pbir         ← byPath → sibling .SemanticModel
    definition/
      report.json
      version.json
      pages/<id>/
        page.json
        visuals/<id>/visual.json
      StaticResources/SharedResources/BaseThemes/CY24SU10.json
```

Both folders must be deployed together to `lpc-v1-app-ldi-pbi-mos`.

### Deployment

1. Copy `output/models/<Name>.SemanticModel/` and `output/models/<Name>.Report/` to `lpc-v1-app-ldi-pbi-mos`
2. Run ALM Toolkit diff
3. Open a PR with `MOSC-####` commit

---

## Repository Structure

```
pbi-automation/
├── generate_reports.py         # report-generator entry point
├── generate_models.py          # model-generator entry point
├── pbi.properties              # report-generator config (workspace, DSNs, keywords)
├── semantic.properties         # model-generator config (Snowflake, dimensions, models)
├── requirements.txt            # combined deps
│
├── report_generator/           # report-generator source package
│   ├── config.py               # reads pbi.properties
│   ├── frd_parser.py           # .docx → structured JSON
│   ├── rdl_generator.py        # JSON → .rdl paginated report XML
│   ├── pbip_generator.py       # JSON → .pbip visual report folders
│   ├── spec_generator.py       # JSON → .md spec files
│   ├── spec_parser.py          # .md spec → report dict (Path B)
│   ├── spec_to_rdl.py          # spec → .rdl (Path B)
│   ├── spec_to_pbip.py         # spec → .pbip (Path B)
│   ├── sql/                    # hand-authored SQL for ODBC reports
│   │   └── 1042_Tax.sql
│   └── templates/
│       ├── MO_Report_Template.rdl  # RDL base template (logo source)
│       └── specs/              # reference spec templates (not parsed by tool)
│
├── model_generator/            # model-generator source package
│   ├── config.py               # reads semantic.properties
│   ├── snowflake_client.py     # Snowflake connection + SHOW COLUMNS introspection
│   ├── tmdl_builder.py         # TMDL content builders (no file I/O)
│   ├── report_builder.py       # .Report content builders (no file I/O)
│   ├── model_generator.py      # orchestrates one model: fetch → build → write
│   ├── DESIGN.md               # model_generator design document
│   ├── dimensions/             # Strategy A YAML files
│   │   ├── dates.yaml
│   │   └── products.yaml
│   └── templates/
│       └── BaseThemes/
│           └── CY24SU10.json   # Power BI theme bundled into every .Report folder
│
├── assets/
│   ├── banner.svg
│   └── pipeline.svg
│
└── output/                     # generated files (not committed)
    ├── json/                   # frd_parsed.json (report-generator)
    ├── specs/                  # .md spec docs (report-generator)
    ├── rdl/                    # .rdl files (report-generator)
    ├── pbip/                   # .pbip folders (report-generator)
    ├── from-spec/              # Path B outputs (report-generator)
    └── models/                 # .SemanticModel + .Report pairs (model-generator)
```

---

## Troubleshooting

### report-generator

**`ModuleNotFoundError: No module named 'docx'`**
The package name is `python-docx`, not `docx`: `pip install python-docx`

**Reports show `"report_format": "Unknown"` in JSON**
The `Report Format` field in the FRD is blank or non-standard. Edit the entry in `output/json/frd_parsed.json`, set it to `"Paginated"` or `"Visual"`, then re-run `--only rdl` or `--only pbip`.

**Wrong datasource type detected**
Check `[datasource_keywords]` in `pbi.properties`. The matched keyword may appear in an unrelated part of the report name or summary. Tighten the phrases or move the report's real keyword higher in the list.

**Wrong semantic model selected**
Update `[model_keywords]` in `pbi.properties` — add a more specific keyword or move that model higher in the list.

**ODBC report has an auto-stub SQL query**
Place a `.sql` file in `report_generator/sql/` named after the report (spaces → underscores) and re-run `--only rdl`. The generator embeds it automatically.

**RDL opens with XML error in Report Builder**
Run `python -c "import xml.etree.ElementTree as ET; ET.parse('output/rdl/path/to/file.rdl')"` to pinpoint the bad line. Check for unescaped `<`, `>`, `&`, or `--` in the report name or requirements fields in the JSON.

### model-generator

**`KeyError: 'model_id'` or model not found**
Run `python generate_models.py --list` to see the exact model IDs configured in `semantic.properties`. The `--model` flag takes the `[model.*]` key (e.g. `financial_daily`), not the display name.

**Snowflake authentication error**
For SSO (`authenticator = externalbrowser`), run from PowerShell on Windows — the browser callback fails in WSL. For user/pass, set both `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD` environment variables.

**`--env d1v1` produces wrong Snowflake account**
Check `[snowflake.d1v1]` in `semantic.properties`. The `.privatelink` suffix is required for dev environments. The account field in the per-env override replaces the base `[snowflake]` account.

**Missing theme file in .Report output**
The generator expects `model_generator/templates/BaseThemes/CY24SU10.json`. If the theme directory is missing, copy it from `lpc-v1-app-ldi-pbi-mos/MO_IntervalSales.Report/StaticResources/SharedResources/BaseThemes/`.

**lineageTag UUIDs change on every run**
Expected behaviour — lineageTag values are regenerated each run and have no semantic meaning in TMDL. ALM Toolkit will show them as changes but they do not affect model functionality.

---

<div align="center">

Built by the **Brightstar Lottery** Performance Wizard team.

[![GitHub](https://img.shields.io/badge/GitHub-avi--igt%2Fpbi--automation-181717?style=flat-square&logo=github)](https://github.com/avi-igt/pbi-automation)
[![MIT License](https://img.shields.io/badge/License-MIT-06d6a0?style=flat-square)](LICENSE)

</div>
