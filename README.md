<div align="center">

<img src="assets/banner.svg" alt="pbi-automation" width="860"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.9%2B-F2C811?style=flat-square&logo=python&logoColor=black)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-06d6a0?style=flat-square)](LICENSE)
[![Power BI](https://img.shields.io/badge/Power%20BI-Fabric-F2C811?style=flat-square&logo=powerbi&logoColor=black)](https://app.powerbi.com)
[![Snowflake](https://img.shields.io/badge/Snowflake-connected-29B5E8?style=flat-square&logo=snowflake&logoColor=white)](https://www.snowflake.com/)

**Three Power BI automation tools for Brightstar Lottery — one repo.**

[Quick Start](#quick-start) · [Pipeline](#pipeline) · [report-generator](#report-generator) · [model-generator](#model-generator) · [bo-converter](#bo-converter) · [Full Lifecycle](#full-development-lifecycle) · [report_generator — How To](#report_generator--how-to) · [model_generator — How To](#model_generator--how-to) · [Utilities](#utilities) · [Repository Structure](#repository-structure) · [Troubleshooting](#troubleshooting) · [Command Reference](command_reference.md)

</div>

---

## What's in this repo

| Tool | Entry point | What it does |
|---|---|---|
| **report-generator** | `generate_reports.py` | FRD `.docx` → `.rdl` paginated reports + `.pbip` visual reports + `.md` spec docs |
| **model-generator** | `generate_models.py` | `semantic.properties` → `.SemanticModel` + `.Report` folder pairs (TMDL, Snowflake-backed) |
| **bo-converter** | `convert_bo_reports.py` | SAP BusinessObjects WebI → `.md` spec files for Path B (`spec_to_rdl.py`) |

All three tools share a single repo, a single `requirements.txt`, and common `templates/` + `output/` directories. They are otherwise independent — each has its own config file and entry point.

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

### bo-converter

```bash
# Extract BO WebI metadata → JSON checkpoint
export BO_PASSWORD=...
python convert_bo_reports.py --only extract

# Generate .md spec files from JSON
python convert_bo_reports.py --only specs

# Full pipeline (extract + specs)
python convert_bo_reports.py

# Filter by folder or report name
python convert_bo_reports.py --folder "Sales Reports"
python convert_bo_reports.py --report "Daily Sales"
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
# Keywords matched (case-insensitive) against report name + summary + notes.
# First match wins.
# default_datasource — fallback when no keyword matches.
#   Values: snowflake | db2 | semantic_model  (default: semantic_model)
default_datasource = semantic_model
snowflake = rdst, tmir, security, transaction
db2       = claims, payments, annuities, debt, setoff, player, ssn, claimant

[model_keywords]
# Keywords matched to select the correct semantic model binding.
# More-specific entries first; last entry is the catch-all default.
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

`config.py` classifies each report by scanning `name + summary + notes` in this order:

1. Scan `[datasource_keywords]` top-to-bottom — first keyword match wins, returning `snowflake` or `db2`.
2. If no keyword matches, return `default_datasource` (configurable; defaults to `semantic_model`).
3. For `semantic_model` reports, `[model_keywords]` selects which semantic model to bind — first match wins, last entry is the catch-all default.

`default_datasource` is the key lever for FRDs where all (or most) reports share the same data source but have generic names that contain no detectable keywords. See [report_generator — How To](#report_generator--how-to) for a worked example.

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
#
# strategy=A  CONFIG-DRIVEN: visible columns and their display names are declared
#             in model_generator/dimensions/<alias>.yaml. Any column not listed is
#             hidden. Use for all DIMCORE tables (ALL_UPPERCASE columns).
#
# strategy=B  AUTO-DISCOVER: all non-primary-key columns are expanded into the
#             fact table with auto-derived display names (SNAKE_CASE → Title Case).
#             Use for small domain tables where you want everything visible.
dates     = DIMCORE.DATES,     primary_key=DATE_KEY,     strategy=A
products  = DIMCORE.PRODUCTS,  primary_key=PRODUCT_KEY,  strategy=A
locations = DIMCORE.LOCATIONS, primary_key=LOCATION_KEY, strategy=A
terminals = DIMCORE.TERMINALS, primary_key=TERMINAL_KEY, strategy=A

[model.financial_daily]
display_name = Financial Daily LDI
fact_table   = FINANCIAL.FINANCIAL_DAILY
dimensions   = dates, products, locations

[model.draw_sales]
display_name  = Draw Sales LDI
fact_table    = DRAW.DRAW_SALES
dimensions    = dates, products, locations
filter_column = BUSINESS_TIMESTAMP    # optional: adds RangeStart/RangeEnd incremental refresh
```

**Non-standard join key:** when the fact table's join column differs from the dimension's `primary_key`, specify it with a colon:
```ini
dimensions = dates, products:GAME_PRODUCT_KEY
```
The generator joins `GAME_PRODUCT_KEY` (fact) → `PRODUCT_KEY` (dim) and the product fields land in the `Products` display folder as normal.

**Role-playing dimension:** add `inherit=<alias>` to reuse an existing dimension's YAML with a different alias and display folder:
```ini
dates_draw = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A, inherit=dates
```
Reference it in the model using the new alias with a join key override:
```ini
dimensions = dates, dates_draw:DRAW_DATE_KEY, products
```

### Fact table column rules

Applied automatically to every fact table column during generation:

| Column | Output |
|---|---|
| Ends with `_KEY` | Hidden `int64` — join key, not surfaced to report authors |
| Ends with `_COUNT` / `_AMOUNT` / `_QUANTITY` | Hidden source column + `CALCULATE(SUM(...))` DAX measure in **`<Table> Measures`** folder (e.g. `Draw Sales Measures`) |
| Everything else | Visible, Title Case display name, in **`<Table> Dims`** folder (e.g. `Draw Sales Dims`) |

Suffix matching is configurable in `[measure_suffixes]` — add new types without any code changes.

### Merged queries (no TMDL relationships)

Dimension data is joined into the fact table via Power Query `Table.NestedJoin` + `Table.ExpandTableColumn`, not TMDL relationships. This means the model works identically with `.rdl` paginated reports and `.pbip` visual reports. Dimension tables are present in Power Query but hidden from the model field pane. All dimension fields appear in the fact table grouped by a display folder named after the dimension alias (`Dates`, `Products`, `Locations`, etc.).

### Output

```
output/models/
  Financial Daily LDI.SemanticModel/
    .platform
    definition.pbism
    definition/
      expressions.tmdl      ← Snowflake connection params + optional RangeStart/RangeEnd
      model.tmdl            ← ref table declarations
      database.tmdl
      tables/
        Financial Daily.tmdl   ← fact table: all columns + merged dimension fields + measures
        Dates.tmdl             ← dimension staging table (isHidden)
        Products.tmdl          ← dimension staging table (isHidden)
        Locations.tmdl         ← dimension staging table (isHidden)

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

No `relationships.tmdl` is generated — dimensions are joined via Power Query merged queries in the fact table's M partition.

Both folders must be deployed together to `lpc-v1-app-ldi-pbi-mos`.

### Deployment

1. Copy `output/models/<Name>.SemanticModel/` and `output/models/<Name>.Report/` to `lpc-v1-app-ldi-pbi-mos`
2. Run ALM Toolkit diff
3. Open a PR with `MOSC-####` commit

---

## bo-converter

Extracts SAP BusinessObjects WebI report metadata via the BO REST API and generates Power BI `.md` spec files for the existing Path B workflow (`spec_to_rdl.py`).

### Configuration

Add a `[bo]` section to `pbi.properties`:

```ini
[bo]
host = http://10.17.56.65:8080/biprws
username = your.name@ourlotto.com
```

Set `BO_PASSWORD` as an environment variable (never in config).

### Pipeline

```
BO REST API
    ↓  Phase 1 (--only extract)
  bo_extractor.py  →  output/bo-extracted/bo_extracted.json
    ↓  Phase 2 (--only specs)
  bo_spec_generator.py  →  output/bo-specs/*.md
    ↓  (existing Path B)
  spec_to_rdl.py  →  output/from-spec/rdl/*.rdl
```

### Workflow

1. `python convert_bo_reports.py --only extract` — Pull metadata from BO
2. Inspect `output/bo-extracted/bo_extracted.json` — Sanity check
3. `python convert_bo_reports.py --only specs` — Generate .md spec files
4. Edit `output/bo-specs/*.md` — Human review, fill in SQL, confirm models
5. `python report_generator/spec_to_rdl.py output/bo-specs/` — Generate .rdl files via Path B

---

## Full Development Lifecycle

pbi-automation handles the first mile — turning requirements into report scaffolding and semantic models. Two companion tools cover the rest of the lifecycle. Each is independent; install only what you need.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 · SCAFFOLD          pbi-automation  (this tool)  · Python · MIT   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  report_generator                                                           │
│  FRD.docx  ──►  frd_parser  ──►  frd_parsed.json  ──►  .rdl / .pbip / .md │
│  Reviewed .md spec  ──────────────────────────────►  .rdl / .pbip          │
│                                                                             │
│  model_generator                                                            │
│  semantic.properties + Snowflake  ──►  .SemanticModel + .Report (TMDL)     │
│                                                                             │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │  .rdl / .pbip / .SemanticModel / .Report on disk
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

# report_generator: FRD → reports
python generate_reports.py "MO FRD v1.0.docx"
# → output/rdl/**/*.rdl   (paginated reports)
# → output/pbip/**/       (visual reports)
# → output/specs/*.md     (review docs)

# Review specs, confirm datasource / SQL / model name, then regenerate
python report_generator/spec_to_rdl.py output/specs/
python report_generator/spec_to_pbip.py output/specs/

# model_generator: semantic.properties → SemanticModel + Report
python generate_models.py --list               # see configured models
python generate_models.py                      # generate all models
# → output/models/<Name>.SemanticModel/
# → output/models/<Name>.Report/

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

## report_generator — How To

### Set a default data source for an FRD

By default, any report whose name and summary contain no keyword from `[datasource_keywords]` is classified as `semantic_model`. Use `default_datasource` to override that fallback for FRDs where all (or most) reports share the same data source.

**Scenario A — Mixed FRD** (Snowflake + DB2 + semantic model reports, e.g. MO Performance Wizard FRD)

Leave the default as-is. Keyword rules handle the known types; the rest fall back to `semantic_model`.

```ini
[datasource_keywords]
default_datasource = semantic_model   # ← default, can be omitted
snowflake = RDST, TMIR, Security
db2       = claim, payment, annuities, debt, player
```

**Scenario B — All-Snowflake FRD** (e.g. TAC Data Examiner Supplemental Document.docx)

Set `default_datasource = snowflake`. Every report that does not match a `db2` keyword will resolve to Snowflake ODBC — including reports with generic names like "Regional Center" or "Balance Report".

```ini
[datasource_keywords]
default_datasource = snowflake
snowflake = RDST, TMIR, Security
db2       = claim, payment, annuities, debt, player
```

Keyword rules still fire first — a report named "TMIR Report" resolves to `snowflake` via keyword, not fallback. `default_datasource` only applies to reports that match nothing.

Valid values: `snowflake` · `db2` · `semantic_model`

---

### Add hand-authored SQL for an ODBC report

For Snowflake ODBC or DB2 reports, the generator produces an auto-stub SQL query with a comment indicating the expected file. To replace it with real SQL:

1. Create a file in `report_generator/sql/` named after the report — spaces become underscores, same root as the `.rdl` output filename:

   ```
   report name:  "1042 Tax"
   SQL file:     report_generator/sql/1042_Tax.sql
   ```

2. Write the query. Parameters referenced in the RDL (`@CalendarYear`, `@StartDate`, `@EndDate`) can be used directly as SQL bind parameters.

3. Re-run the generator — the file is picked up automatically, no config change needed:

   ```bash
   python generate_reports.py --only rdl --report "1042 Tax"
   ```

If no `.sql` file is found, the generator falls back to `SELECT * FROM <table> -- TODO` and logs the expected path.

---

### Override a wrongly-detected data source

If `infer_datasource()` picks the wrong type for a specific report, there are two options:

**Option 1 — Tighten the keyword** (preferred for systematic fixes)

Make the keyword more specific so it no longer matches the wrong report, or add a more-specific entry above the broad one:

```ini
[datasource_keywords]
default_datasource = semantic_model
snowflake = RDST, TMIR, Security    # tighten: remove "Security" if it causes false positives
db2       = claim, payment, annuities, debt
```

**Option 2 — Edit the JSON checkpoint** (for one-off fixes)

After `--only parse`, edit `output/json/frd_parsed.json` and change the `"datasource_type"` field for the affected report, then re-run `--only rdl` or `--only pbip`. The JSON is the human checkpoint exactly for this reason.

---

## model_generator — How To

### Add a new dimension table

This is the complete procedure for wiring a new dimension (e.g. `DRAW.DRAW_INFORMATION`) into one or more semantic models.

**Step 1 — Register the dimension in `semantic.properties`**

Add a line to the `[dimensions]` section:

```ini
[dimensions]
dates            = DIMCORE.DATES,         primary_key=DATE_KEY,      strategy=A
products         = DIMCORE.PRODUCTS,      primary_key=PRODUCT_KEY,   strategy=A
locations        = DIMCORE.LOCATIONS,     primary_key=LOCATION_KEY,  strategy=A
terminals        = DIMCORE.TERMINALS,     primary_key=TERMINAL_KEY,  strategy=A
draw_information = DRAW.DRAW_INFORMATION, primary_key=DRAW_INFO_KEY, strategy=A  # ← new
```

- `alias` (`draw_information`) becomes the Power Query table name (`Draw Information`), the TMDL file name (`Draw Information.tmdl`), and the display folder in the model field pane.
- `primary_key` is the column in the dimension table used for the join.
- `strategy=A` means you control which columns are visible via a YAML file (recommended). `strategy=B` auto-expands all non-key columns using auto-derived display names.

**Step 2 — Create the dimension YAML** *(Strategy A only)*

Create `model_generator/dimensions/draw_information.yaml`:

```yaml
# draw_information.yaml — visible columns for DRAW.DRAW_INFORMATION (Strategy A)
# DRAW_INFO_KEY is excluded (primary key, always hidden automatically)

visible_columns:
  DRAW_NUMBER:           Draw Number
  DRAW_DATE:             Draw Date
  DRAW_DESCRIPTION:      Draw Description
  JACKPOT_AMOUNT:        Jackpot Amount
  CURRENT_DRAW_IND:      Is Current Draw
  # add more columns as needed
```

Only columns listed here are expanded into the fact table and shown in the model field pane. Any column not listed is silently excluded from the expand step.

For `strategy=B`, skip this file entirely — all non-key columns are auto-expanded with `SNAKE_CASE → Title Case` display names.

**Step 3 — Add the dimension to the model**

In the relevant `[model.*]` section, append the alias to the `dimensions` list:

```ini
[model.draw_sales]
display_name  = Draw Sales LDI
fact_table    = DRAW.DRAW_SALES
dimensions    = dates, products, locations, draw_information  # ← appended
filter_column = BUSINESS_TIMESTAMP
```

If the fact table's join column has a **different name** from the dimension's `primary_key`, add a colon override:

```ini
dimensions = dates, products, locations, draw_information:FACT_DRAW_INFO_KEY
#                                                          ↑ fact column name
```

This joins `FACT_DRAW_INFO_KEY` (fact) → `DRAW_INFO_KEY` (dim) while keeping the dimension's primary key as declared.

**Step 4 — Regenerate**

```bash
python generate_models.py --model draw_sales
```

The generated fact table M query will gain two new steps:

```powerquery
#"Merged Draw Information" = Table.NestedJoin(prev, {"DRAW_INFO_KEY"},
    #"Draw Information", {"DRAW_INFO_KEY"}, "Draw Information", JoinKind.LeftOuter),
#"Expanded Draw Information" = Table.ExpandTableColumn(#"Merged Draw Information",
    "Draw Information", {"DRAW_NUMBER", "DRAW_DATE", ...}, {"Draw Number", "Draw Date", ...})
```

And the expanded columns will appear in a **Draw Information** display folder in the model field pane.

---

### Add a new semantic model

**Step 1 — Add a `[model.*]` section to `semantic.properties`**

```ini
[model.my_new_model]
display_name = My New Model LDI
fact_table   = SCHEMA.FACT_TABLE
dimensions   = dates, products, locations   # use any registered dimension aliases
```

`display_name` must end with `LDI`, `RSM`, or `RPT` (handbook requirement). The name minus the postfix becomes the Power Query table name and TMDL file name.

**Step 2 — Add a `filter_column` if the fact table has a timestamp column** *(optional)*

```ini
filter_column = BUSINESS_TIMESTAMP
```

This adds `RangeStart` / `RangeEnd` parameters to `expressions.tmdl` and a `Table.SelectRows` filter step in the fact table's M query, enabling incremental refresh in Fabric.

**Step 3 — Generate**

```bash
python generate_models.py --model my_new_model
```

---

### Add or change a measure suffix

Fact columns ending with the configured suffixes are automatically converted to hidden source columns with a `CALCULATE(SUM(...))` DAX measure in the **`<Table> Measures`** display folder (e.g. `Draw Sales Measures`).

To add a new suffix, edit `[measure_suffixes]` in `semantic.properties`:

```ini
[measure_suffixes]
_COUNT    = int64,   0
_AMOUNT   = decimal, #,##0.00
_QUANTITY = int64,   #,##0
_WEIGHT   = decimal, #,##0.000   # ← new: any column ending _WEIGHT gets a measure
```

No code changes required. Regenerate to apply.

---

## Utilities

### `clean.py` — wipe generated output

Generated files accumulate across runs. Use `clean.py` to wipe output directories before a fresh regeneration, or to remove stale artifacts before deployment.

```bash
python clean.py output              # wipe all output/ subdirectories
python clean.py output --rdl        # wipe output/rdl/ only
python clean.py output --pbip       # wipe output/pbip/ only
python clean.py output --models     # wipe output/models/ only
python clean.py output --specs      # wipe output/specs/ only
python clean.py output --json       # wipe output/json/ only
python clean.py output --from-spec  # wipe output/from-spec/ only
python clean.py sql                 # wipe report_generator/sql/ (prompts for confirmation)
python clean.py sql --yes           # skip confirmation prompt
python clean.py output sql          # wipe both output/ and sql/ in one command
python clean.py --dry-run output    # preview what would be deleted without deleting
```

> **Note on `clean.py sql`:** `report_generator/sql/` contains hand-authored SQL files that are not regenerated automatically. The `sql` target always prompts for confirmation unless `--yes` is passed. Use `--dry-run` to review what would be removed first.

---

## Repository Structure

```
pbi-automation/
├── generate_reports.py         # report-generator entry point
├── generate_models.py          # model-generator entry point
├── clean.py                    # utility: wipe output/ and/or report_generator/sql/
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
│   ├── dimensions/             # Strategy A YAML files (one per dimension alias)
│   │   ├── dates.yaml
│   │   ├── products.yaml
│   │   ├── locations.yaml
│   │   └── terminals.yaml
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
