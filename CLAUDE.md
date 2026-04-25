# CLAUDE.md — pbi-automation

## What This Repo Does

`pbi-automation` is a mono-repo containing three complementary Power BI generation tools:

| Tool | Entry point | Purpose |
|---|---|---|
| **report_generator** | `generate_reports.py` | FRD (.docx) → `.rdl` paginated reports + `.pbip` visual reports |
| **model_generator** | `generate_models.py` | `semantic.properties` → `.SemanticModel` + `.Report` folder pairs |
| **bo_converter** | `convert_bo_reports.py` | SAP BusinessObjects WebI → `.md` specs + `.rdl` reports + `.sql` extracted queries |

All tools write to `output/` and deploy to `lpc-v1-app-ldi-pbi-mos`.

---

## Repo Structure

```
pbi-automation/
├── generate_reports.py         ← report_generator entry point
├── generate_models.py          ← model_generator entry point
├── convert_bo_reports.py       ← bo_converter entry point
├── pbi.properties              ← report_generator + bo_converter config
├── semantic.properties         ← model_generator config (Snowflake, dimensions, models)
├── requirements.txt            ← combined dependencies
│
├── report_generator/           ← FRD → RDL/PBIP pipeline
│   ├── config.py               ← reads pbi.properties
│   ├── frd_parser.py           ← .docx → structured JSON
│   ├── rdl_generator.py        ← JSON → .rdl (paginated reports)
│   ├── pbip_generator.py       ← JSON → .pbip (visual reports)
│   ├── spec_generator.py       ← JSON → .md spec docs
│   ├── spec_parser.py          ← .md spec → structured dict (Path B)
│   ├── spec_to_rdl.py          ← spec → .rdl (Path B)
│   ├── spec_to_pbip.py         ← spec → .pbip (Path B)
│   ├── sql/                    ← hand-authored SQL for ODBC reports
│   └── templates/
│       ├── MO_Report_Template.rdl  ← RDL base template (logo source)
│       └── specs/              ← spec reference templates
│
├── model_generator/            ← semantic.properties → SemanticModel + Report
│   ├── config.py               ← reads semantic.properties → typed dataclasses
│   ├── snowflake_client.py     ← Snowflake connection + column introspection
│   ├── tmdl_builder.py         ← TMDL content builders
│   ├── report_builder.py       ← .Report content builders
│   ├── model_generator.py      ← orchestrates one model end-to-end
│   ├── DESIGN.md               ← full design document for model_generator
│   ├── dimensions/             ← Strategy A YAML files
│   │   ├── dates.yaml
│   │   └── products.yaml
│   └── templates/
│       └── BaseThemes/
│           └── CY24SU10.json   ← Power BI theme
│
├── bo_converter/               ← SAP BO WebI → PBI specs + RDL
│   ├── config.py               ← reads [bo] section from pbi.properties
│   ├── bo_client.py            ← BO REST API client (auth, enumerate, extract)
│   ├── bo_extractor.py         ← Phase 1: enumerate + extract + write JSON/SQL
│   └── bo_spec_generator.py    ← Phase 2: JSON → .md specs (delegates to spec_generator)
│
└── output/
    ├── json/                   ← frd_parsed.json (report_generator)
    ├── specs/                  ← .md spec docs (report_generator)
    ├── rdl/                    ← .rdl files (report_generator)
    ├── pbip/                   ← .pbip folders (report_generator)
    ├── from-spec/              ← Path B outputs (report_generator)
    ├── models/                 ← .SemanticModel + .Report pairs (model_generator)
    ├── bo-extracted/           ← bo_extracted.json (bo_converter Phase 1)
    ├── bo-sql/                 ← extracted SQL files (bo_converter Phase 1)
    ├── bo-specs/               ← .md spec files (bo_converter Phase 2)
    └── bo-rdl/                 ← .rdl files (bo_converter Phase 3)
```

---

## Tool 1 — report_generator

### Run

```bash
python generate_reports.py                          # full pipeline: FRD → RDL + PBIP + specs
python generate_reports.py --only parse             # step 1 only: FRD → JSON
python generate_reports.py --only rdl               # step 2 only: JSON → .rdl
python generate_reports.py --only pbip              # step 3 only: JSON → .pbip
python generate_reports.py --only spec              # step 4 only: JSON → .md specs
python generate_reports.py --report "Tax"           # filter by report name
python generate_reports.py path/to/FRD.docx         # explicit FRD path
```

### Pipeline

```
FRD.docx → frd_parser → JSON → rdl_generator  → output/rdl/
                              → pbip_generator → output/pbip/
                              → spec_generator → output/specs/
```

Path B (spec-first review workflow):
```
(edit output/specs/*.md) → spec_to_rdl  → output/from-spec/rdl/
                         → spec_to_pbip → output/from-spec/pbip/
```

### Configuration (`pbi.properties`)

```ini
workspace = Missouri - D1V1

[datasource_keywords]
default_datasource = semantic_model   # fallback when no keyword matches (snowflake|db2|semantic_model)
snowflake = rdst, tmir, security, transaction
db2 = claims, payments, annuities, debt

[model_keywords]
MO_Sales = sales, validations, cancels
MO_DrawData = draw, game
MO_CoreTables = retailer list, chain store   # last entry = default fallback

[odbc]
db2_dsn = MOS-Q1-BOADB
sfodbc_dsn = MOS-PX-SFODBC

[snowflake_native]
host = igtgloballottery-igtpxv1_ldi.privatelink.snowflakecomputing.com
implementation = 2.0
```

**Never hardcode** DSN names, workspace names, or dataset names — always read from
`pbi.properties` via `report_generator/config.py`.

### Data Source Detection Logic

`infer_datasource()` (`config.py`) classifies each report in priority order:

1. Scan `[datasource_keywords]` top-to-bottom — match against report `name + summary + notes` (case-insensitive). First match wins and returns that type (`snowflake` or `db2`).
2. If no keyword matches, return `default_datasource` (defaults to `semantic_model` if not set).

The `default_datasource` key in `[datasource_keywords]` controls the fallback:

| Scenario | Setting |
|---|---|
| Mixed FRD (Snowflake + DB2 + semantic model reports) | `default_datasource = semantic_model` (default) |
| All reports in the FRD are Snowflake SQL-based | `default_datasource = snowflake` |
| All reports in the FRD are DB2-based | `default_datasource = db2` |

**Example — TAC Data Examiner FRD** (all reports are Snowflake ODBC, but most names contain no detectable keywords):
```ini
[datasource_keywords]
default_datasource = snowflake
snowflake = RDST, TMIR, Security
db2       = claim, payment, annuities, debt
```
Keyword rules still fire first — a report named "TMIR Report" still resolves to `snowflake` via keyword, not fallback. `default_datasource` only applies to reports that match nothing.

### FRD Parsing Notes

- The FRD uses **Azure DevOps SDT content controls** in Word — use `lxml` to parse
  `w:sdt` elements, not plain paragraph text
- Work item headers follow pattern: `MO-XXXXX,Draft,Functional/Business - ` — strip
  this prefix
- `Report Format` field determines output type: `paginated`/`RDL` → `.rdl`,
  `Power BI`/`visual` → `.pbip`
- SQL layering: if `report_generator/sql/<ReportName>.sql` exists, it overrides the auto-generated
  dataset query

---

## Tool 2 — model_generator

### Run

```bash
python generate_models.py                           # generate all configured models
python generate_models.py --model financial_daily   # generate one model
python generate_models.py --list                    # list all configured models
python generate_models.py --env d1v1                # target environment

# SSO credentials (PowerShell — SSO requires native Windows Python)
$env:SNOWFLAKE_USER = "your.name@ourlotto.com"
py generate_models.py

# Username/password credentials (bash/WSL)
export SNOWFLAKE_USER=your_username
export SNOWFLAKE_PASSWORD=your_password
```

Output goes to `output/models/`. Each model produces a `.SemanticModel` + `.Report`
folder pair.

### Configuration (`semantic.properties`)

Four section types:
- `[snowflake]` / `[snowflake.<env>]` — connection details + per-env overrides
- `[measure_suffixes]` — configurable suffix → TMDL type + format mapping
- `[dimensions]` — conformed dimension registry (`alias = SCHEMA.TABLE, primary_key=..., strategy=A|B`)
- `[model.*]` — one section per semantic model (`display_name`, `fact_table`, `dimensions`)

Non-standard join keys: `dimensions = dates, products:GAME_PRODUCT_KEY`
Role-playing dimensions: `inherit=<alias>` to reuse Strategy A YAML

Full design doc: `model_generator/DESIGN.md`

### Star Schema Rules

Fact table columns are classified in priority order:

| Column | Becomes |
|---|---|
| Name ends with `_KEY` | Hidden, `int64` (join key — no relationship, joined via M query) |
| Ends in `_COUNT` / `_AMOUNT` / `_QUANTITY` (configurable) | Hidden source column + `CALCULATE(SUM(...))` measure under `<Table> Measures` display folder (e.g. `Draw Sales Measures`) |
| Anything else | Visible, Title Case display name, in `<Table> Dims` display folder (e.g. `Draw Sales Dims`) |

Dimension columns are expanded into the fact table via Power Query merged queries (`Table.NestedJoin` + `Table.ExpandTableColumn`). Each dimension's columns appear under a display folder named after the dimension (e.g. `Dates`, `Products`). No `relationships.tmdl` is generated.

If two dimensions expose a column with the same display name (e.g. both Products and Locations have `Settle Class Code`), the generator automatically prefixes with the dimension name: `Products Settle Class Code`, `Locations Settle Class Code`.

---

## Tool 3 — bo_converter

### Run

```bash
export BO_PASSWORD=...
python convert_bo_reports.py                        # full pipeline (extract + specs + rdl)
python convert_bo_reports.py --only extract         # Phase 1: BO API -> JSON + SQL
python convert_bo_reports.py --only specs           # Phase 2: JSON -> .md specs
python convert_bo_reports.py --only rdl             # Phase 3: .md specs -> .rdl files
python convert_bo_reports.py --folder "CAP"         # filter by folder (comma-separated)
python convert_bo_reports.py --report "Daily Sales" # filter by report name
```

### Configuration (`pbi.properties` — `[bo]` section)

```ini
[bo]
host = http://10.17.56.65:8080/biprws
username = administrator
# Password via BO_PASSWORD env var — never stored here
# Comma-separated folder paths. CLI --folder overrides.
root_folder = Public Folder/Connecticut/Reports
```

### Pipeline

```
BO REST API
    |  Phase 1 (--only extract)
  bo_extractor.py  ->  output/bo-extracted/bo_extracted.json + output/bo-sql/*.sql
    |  Phase 2 (--only specs)
  bo_spec_generator.py  ->  output/bo-specs/*.md
    |  Phase 3 (--only rdl)
  spec_to_rdl.py  ->  output/bo-rdl/*.rdl
```

Phase 2 delegates to `report_generator.spec_generator` for markdown rendering.
Phase 3 delegates to `report_generator.spec_to_rdl` (existing Path B).

### Multi-folder support

Both `root_folder` config and `--folder` CLI accept comma-separated paths:
```ini
root_folder = Public Folder/Connecticut/Reports, User Folders/Administrator/Julia
```

### SQL extraction

Phase 1 extracts the SQL behind each BO data provider into `output/bo-sql/`. Each `.sql` file
includes headers: data provider name, universe, data source type, and custom SQL flag.

---

## Output and Deployment

| Tool | Output folder | Deploy target |
|---|---|---|
| report_generator | `output/rdl/`, `output/pbip/` | `lpc-v1-app-ldi-pbi-mos` via Fabric CI/CD |
| model_generator | `output/models/` | `lpc-v1-app-ldi-pbi-mos` via ALM Toolkit + PR |
| bo_converter | `output/bo-rdl/`, `output/bo-specs/` | `lpc-v1-app-ldi-pbi-mos` via Fabric CI/CD |

Commit convention for deployment PRs: `MOSC-#### description`

---

## Related Repos

| Repo | Relationship |
|---|---|
| `lpc-v1-app-ldi-pbi-mos` | Deployment target — all generated artifacts go here |
| `pbi-cli` | Validates generated models via DAX queries against running PBI Desktop |

---

## Environment

- Platform: Microsoft Fabric + Power BI Premium capacity
- `report_generator` deps: `python-docx`, `lxml`
- `model_generator` deps: `snowflake-connector-python`, `PyYAML`
- `bo_converter` deps: `requests` (+ reuses `report_generator` for spec/RDL generation)
- WSL2 + Windows Python (`py.exe`) for SSO Snowflake auth
- Output is for manual review — do not auto-publish to Fabric/Power BI service
