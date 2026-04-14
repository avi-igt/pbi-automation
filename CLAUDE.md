# CLAUDE.md — pbi-automation

## What This Repo Does

`pbi-automation` is a mono-repo containing two complementary Power BI generation tools:

| Tool | Entry point | Purpose |
|---|---|---|
| **report_generator** | `generate_reports.py` | FRD (.docx) → `.rdl` paginated reports + `.pbip` visual reports |
| **model_generator** | `generate_models.py` | `semantic.properties` → `.SemanticModel` + `.Report` folder pairs |

Both tools write to `output/` and deploy to `lpc-v1-app-ldi-pbi-mos`.

---

## Repo Structure

```
pbi-automation/
├── generate_reports.py         ← report_generator entry point
├── generate_models.py          ← model_generator entry point
├── pbi.properties              ← report_generator config (workspace, DSNs, keywords)
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
└── output/
    ├── json/                   ← frd_parsed.json (report_generator)
    ├── specs/                  ← .md spec docs (report_generator)
    ├── rdl/                    ← .rdl files (report_generator)
    ├── pbip/                   ← .pbip folders (report_generator)
    ├── from-spec/              ← Path B outputs (report_generator)
    └── models/                 ← .SemanticModel + .Report pairs (model_generator)
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
| Ends in `_COUNT` / `_AMOUNT` / `_QUANTITY` (configurable) | Hidden source column + `CALCULATE(SUM(...))` measure under `Base Measures` display folder |
| Anything else | Visible, in root of field pane |

Dimension columns are expanded into the fact table via Power Query merged queries (`Table.NestedJoin` + `Table.ExpandTableColumn`). Each dimension's columns appear under a display folder named after the dimension (e.g. `Dates`, `Products`). No `relationships.tmdl` is generated.

If two dimensions expose a column with the same display name (e.g. both Products and Locations have `Settle Class Code`), the generator automatically prefixes with the dimension name: `Products Settle Class Code`, `Locations Settle Class Code`.

---

## Output and Deployment

| Tool | Output folder | Deploy target |
|---|---|---|
| report_generator | `output/rdl/`, `output/pbip/` | `lpc-v1-app-ldi-pbi-mos` via Fabric CI/CD |
| model_generator | `output/models/` | `lpc-v1-app-ldi-pbi-mos` via ALM Toolkit + PR |

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
- WSL2 + Windows Python (`py.exe`) for SSO Snowflake auth
- Output is for manual review — do not auto-publish to Fabric/Power BI service
