# pbi-model-generator — Design Document

## Purpose

A config-driven command-line tool that generates complete Power BI `.SemanticModel`
and companion `.Report` folder structures (TMDL / PBIP format) from a
`semantic.properties` configuration file.

The tool is **generic** — it has no opinion about which models exist. The user declares
a fact table, a dimension list, and the tool produces a deployment-ready star schema
semantic model paired with a placeholder report. Adding a new model is a config
change, not a code change.

Output is committed to `lpc-v1-app-ldi-pbi-mos` and deployed via the standard
Fabric CI/CD pipeline.

---

## How the Tool Runs

```bash
python generate.py                             # generate all [model.*] sections
python generate.py --model financial_daily     # generate one model only
python generate.py --list                      # list all configured models
python generate.py --env d1v1                  # target a specific environment
```

One run generates every model declared in `semantic.properties`. Each model produces
one `.SemanticModel` folder and one `.Report` folder under `output/`. On every run
both output folders are fully regenerated from scratch — no incremental patching.

ALM Toolkit diff in the pull request review catches any unintended changes before merge.

---

## Configuration — `semantic.properties`

All input to the tool lives in `semantic.properties`. No model definitions are
hardcoded in the generator.

### `[snowflake]` — connection details

```ini
[snowflake]
account       = igtgloballottery-igtpxv1_ldi
warehouse     = lpcdxv1_wh_ldi
database      = MOSQ1V1_DB_DH
role          = mosq1v1_ru_datareader
authenticator = externalbrowser   # externalbrowser = SSO | snowflake = username+password
```

Credentials are never stored in this file. They are read from environment variables
at runtime:

```bash
# SSO (recommended) — only username required
export SNOWFLAKE_USER=your.name@ourlotto.com

# Username/password
export SNOWFLAKE_USER=your_username
export SNOWFLAKE_PASSWORD=your_password
```

When `authenticator = externalbrowser`, a browser window opens for the SSO flow.
`SNOWFLAKE_PASSWORD` is not required and is ignored.

> **WSL note:** SSO browser callbacks do not work when running through WSL's
> Windows interop. Run from native PowerShell: `$env:SNOWFLAKE_USER = "..."` then
> `py generate.py ...`

### `[snowflake.<env>]` — per-environment overrides

Any key in a `[snowflake.<env>]` section overrides the matching key from `[snowflake]`.
Unspecified keys fall back to the base section.

```ini
[snowflake.d1v1]
account   = igtgloballottery-igtd2v1_ldi.privatelink
warehouse = lpcdxv1_wh_ldi
database  = MOSQ1V1_DB_DH

[snowflake.c1v1]
account   = igtgloballottery-igtcxv1_ldi
warehouse = WH_LDI_XS
database  = MOSQ1V1_DB_DH

[snowflake.p1v1]
account   = igtgloballottery-igtpxv1_ldi
warehouse = WH_LDI_M
database  = MOSQ1V1_DB_DH
```

### `[measure_suffixes]` — configurable measure creation

Declares which column name suffixes trigger hidden source columns with auto-generated
DAX measures. Format: `SUFFIX = tmdl_type, format_string`

```ini
[measure_suffixes]
_COUNT    = int64,   0
_AMOUNT   = decimal, #,##0.00
_QUANTITY = int64,   #,##0
```

If this section is omitted, the three defaults above are used automatically. New
suffixes can be added at any time without code changes. The TMDL output organises
hidden columns and measures into labelled sections per suffix.

### `[dimensions]` — conformed dimension table declarations

```ini
[dimensions]
dates      = DIMCORE.DATES,     primary_key=DATE_KEY,     strategy=A
products   = DIMCORE.PRODUCTS,  primary_key=PRODUCT_KEY,  strategy=A
locations  = DIMCORE.LOCATIONS, primary_key=LOCATION_KEY, strategy=B
terminals  = DIMCORE.TERMINALS, primary_key=TERMINAL_KEY, strategy=B
```

Each dimension entry declares:
- The Snowflake source table (`SCHEMA.TABLE`)
- The primary key column used for relationships (`primary_key`)
- The column visibility strategy (`strategy`, default: `A`)
- Optionally, `inherit=<alias>` for role-playing dimensions (see below)

### `[model.*]` — one section per semantic model

```ini
[model.financial_daily]
display_name = Financial Daily LDI
fact_table   = FINANCIAL.FINANCIAL_DAILY
dimensions   = dates, products, locations, terminals

[model.invoice_detail]
display_name = Invoice Detail LDI
fact_table   = FINANCIAL.INVOICE_DETAIL
dimensions   = dates, products, locations

[model.draw_sales]
display_name = Draw Sales LDI
fact_table   = DRAW.DRAW_SALES
dimensions   = dates, products, locations
```

`display_name` becomes the Power BI model name and folder name. It must follow the
handbook naming standard: Title Case + mandatory postfix (LDI / RSM / RPT).

---

## Non-Standard Fact Join Keys

By default the tool assumes the fact table joins to each dimension using the
dimension's own `primary_key` column. When the fact table uses a different column
name, declare it with `alias:FACT_COLUMN` syntax:

```ini
[model.order_detail]
display_name = Order Detail LDI
fact_table   = INSTANT.ORDER_DETAILS
dimensions   = dates, products:GAME_PRODUCT_KEY
#  → fromColumn: GAME_PRODUCT_KEY, toColumn: PRODUCT_KEY
```

The generated relationship uses `GAME_PRODUCT_KEY` as the `fromColumn` in the fact
table and `PRODUCT_KEY` as the `toColumn` in the dimension.

---

## Role-Playing Dimensions

When a fact table joins to the same physical dimension table more than once (e.g.
`FIRST_VALIDATION_DATE_KEY` and `LAST_VALIDATION_DATE_KEY` both join to
`DIMCORE.DATES`), declare each join as a separate alias with a custom fact key.

To avoid duplicating the Strategy A YAML, use `inherit=<alias>` to reuse the parent
alias's YAML file:

```ini
[dimensions]
dates            = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A
dates_first_val  = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A, inherit=dates
dates_last_val   = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A, inherit=dates

[model.inventory_detail]
display_name = Inventory Detail LDI
fact_table   = INSTANT.INVENTORY_DETAIL
dimensions   = dates_first_val:FIRST_VALIDATION_DATE_KEY, dates_last_val:LAST_VALIDATION_DATE_KEY, products, locations
```

Each alias produces an independent TMDL table with its own display name
(`Dates First Val`, `Dates Last Val`) and its own relationship entry, while reading
column visibility from the shared `model_generator/dimensions/dates.yaml`.

---

## Star Schema Generation Rules

### Fact Table

The tool connects to Snowflake and runs `SHOW COLUMNS IN TABLE <schema>.<table>` to
retrieve the full column list. Rules are applied in priority order:

| Column pattern | TMDL output | DAX measure created |
|---|---|---|
| Exact match on a dimension join key (default or overridden) | Hidden column, `dataType: int64`, `summarizeBy: none` | None — used for relationship only |
| Ends in `_COUNT` (configurable) | Hidden column, `dataType: int64`, `summarizeBy: none` | `CALCULATE(SUM(...))`, format `"0"`, folder `"Base Measures"` |
| Ends in `_AMOUNT` (configurable) | Hidden column, `dataType: decimal`, `summarizeBy: none` | `CALCULATE(SUM(...))`, format `"#,##0.00"`, folder `"Base Measures"` |
| Ends in `_QUANTITY` (configurable) | Hidden column, `dataType: int64`, `summarizeBy: none` | `CALCULATE(SUM(...))`, format `"#,##0"`, folder `"Base Measures"` |
| Any other `ALL_UPPERCASE` column | Hidden column, `summarizeBy: none` | None |
| `Title Case` column | Visible column | None |

Key column matching is **exact name only**. If a fact table has `BILL_TO_LOCATION_KEY`
but not `LOCATION_KEY`, the column is treated as a regular hidden column with no
relationship — unless an `alias:BILL_TO_LOCATION_KEY` override is declared.

### Dimension Tables

Dimension tables are generated in **Import mode** (small tables, daily refresh).
All columns are hidden by default; visibility is controlled by the strategy setting.

### Relationships

One active, single-direction relationship per dimension in the model's `dimensions`
list. Uses the dimension's `primary_key` as `toColumn`; uses the fact table's
matching column (default `primary_key`, or the `alias:FACT_KEY` override) as
`fromColumn`.

```
DIMCORE.DATES.DATE_KEY          →  FactTable.DATE_KEY          (active, datePartOnly)
DIMCORE.PRODUCTS.PRODUCT_KEY    →  FactTable.PRODUCT_KEY       (active)
DIMCORE.LOCATIONS.LOCATION_KEY  →  FactTable.LOCATION_KEY      (active)
```

`joinOnDateBehavior: datePartOnly` is automatically added for the `dates` dimension
because `DATE_KEY` is stored as a NUMBER in Snowflake, not a DATE.

If a resolved join column is not present in the fact table, the tool emits a warning
and skips that relationship.

### Measure Naming

Source column name → measure name: lowercase all, split on `_`, capitalise each word.

```
SALES_COUNT                        →  Sales Count
VALIDATION_BASED_SALES_AMOUNT      →  Validation Based Sales Amount
PLAYER_CARD_ONLINE_QUANTITY        →  Player Card Online Quantity
```

All base measures go into `displayFolder: "Base Measures"`. Derived measures (YTD,
PY, ratios) are authored manually after generation.

---

## Dimension Column Visibility Strategies

### Strategy A — Config-driven (default)

You explicitly list which columns should be visible in a YAML file at
`model_generator/dimensions/<alias>.yaml`. Every column not in that list is hidden. The right-hand
value is the business display name shown in the Power BI field pane.

```yaml
# model_generator/dimensions/dates.yaml
visible_columns:
  CALENDAR_DATE:         Date
  CALENDAR_YEAR:         Year
  CALENDAR_MONTH_NUMBER: Month Number
  CALENDAR_MONTH_NAME:   Month Name
  CALENDAR_QUARTER:      Quarter
  FISCAL_YEAR:           Fiscal Year
  FISCAL_QUARTER:        Fiscal Quarter
  FISCAL_WEEK_NUMBER:    Fiscal Week
```

If the YAML file is missing, the tool warns and hides all dimension columns. The
model still generates correctly. Role-playing aliases with `inherit=<alias>` reuse
the parent's YAML — no duplication needed.

**When to use:** All `DIMCORE` dimensions (they use `ALL_UPPERCASE` columns throughout,
so Strategy B would hide everything).

### Strategy B — Snowflake introspection

The tool retrieves the full column list from Snowflake at runtime and applies a naming
convention rule automatically:

- `Title_Case` or `Mixed Case` column names → **visible**
- `ALL_UPPERCASE_WITH_UNDERSCORES` → **hidden**

No YAML file required. The Snowflake column name becomes the display name.

**When to use:** Dimensions that already use business-friendly mixed-case column names.
Not suitable for `DIMCORE` tables (all uppercase — everything would be hidden).

---

## Output Structure

Each model generates a matched pair of folders under `output/`:

```
output/
├── Financial Daily LDI.SemanticModel/
│   ├── .platform                         ← Fabric metadata (type, displayName, logicalId GUID)
│   ├── definition.pbism                  ← PBISM version manifest
│   └── definition/
│       ├── database.tmdl                 ← compatibilityLevel: 1605
│       ├── model.tmdl                    ← culture, ref tables
│       ├── expressions.tmdl             ← Snowflake connection parameters
│       ├── relationships.tmdl           ← auto-generated from dimension list
│       └── tables/
│           ├── Financial Daily.tmdl     ← fact table: columns + measures
│           ├── Dates.tmdl
│           ├── Products.tmdl
│           ├── Locations.tmdl
│           └── Terminals.tmdl
│
└── Financial Daily LDI.Report/
    ├── .platform                         ← Fabric metadata (type: Report, logicalId GUID)
    ├── definition.pbir                   ← byPath reference to sibling .SemanticModel
    ├── .pbi/
    │   └── localSettings.json            ← minimal, no remoteArtifacts
    └── definition/
        ├── report.json                   ← CY24SU10 theme, report-level settings
        ├── version.json
        ├── pages/
        │   ├── pages.json
        │   └── <pageId>/
        │       ├── page.json             ← 1280×720 placeholder page
        │       └── visuals/<visualId>/
        │           └── visual.json       ← single textbox: "intentionally left blank"
        └── StaticResources/
            └── SharedResources/
                └── BaseThemes/
                    └── CY24SU10.json     ← copied from model_generator/templates/BaseThemes/
```

Both folders in a pair are committed and deployed together to `lpc-v1-app-ldi-pbi-mos`.
The `.Report` folder's `definition.pbir` uses a relative `byPath` reference to bind to
its sibling `.SemanticModel`, so the pair must always be in the same parent directory.

### `expressions.tmdl` parameters

```tmdl
expression SnowflakeServer    = "igtgloballottery-igtpxv1_ldi.snowflakecomputing.com" ...
expression SnowflakeWarehouse = "lpcdxv1_wh_ldi" ...
expression SnowflakeRole      = "mosq1v1_ru_datareader" ...
expression SnowflakeDBName    = "MOSQ1V1_DB_DH" ...
```

The server hostname is built as `{account}.snowflakecomputing.com` from the config
value. For privatelink accounts (e.g. d1v1), the `.privatelink` suffix is already
part of the `account` value, producing the correct hostname automatically.

---

## Multi-Environment Support

```bash
python generate.py --env d1v1    # development (privatelink)
python generate.py --env c1v1    # certification / UAT
python generate.py --env p1v1    # production
```

Environment-specific values override the base `[snowflake]` section for the current
run. The generated `expressions.tmdl` contains the env-specific server and warehouse
values. Running without `--env` uses the base `[snowflake]` section (production by
default).

---

## Handbook Compliance

All generated artifacts comply with the Power BI Developer Handbook & Guide:

| Handbook rule | How enforced |
|---|---|
| Semantic model names: Title Case + postfix (LDI/RSM/RPT) | `display_name` in `[model.*]` — validated at startup |
| User-facing objects: Title Case, no technical prefixes | Measure names converted from SNAKE_CASE automatically |
| Hidden technical objects: ALL_UPPERCASE, `summarizeBy: none` | Applied to all source columns automatically |
| Snowflake native connector (ADBC 2.0) | M query template uses `Snowflake.Databases(..., [Implementation="2.0"])` |
| Connection parameters in `expressions.tmdl` | Never hardcoded — always from config |
| Single-direction relationships | All relationships generated dimension → fact |
| PBIP/TMDL format only | Output is TMDL — no `.pbix` generated |

---

## What This Tool Does Not Do

- Does not generate derived measures (YTD, PY, ratios, KPIs) — those are authored
  manually in Tabular Editor after the base model is deployed
- Does not generate RLS roles
- Does not deploy to Fabric — output is files for Git commit and CI/CD pipeline
- Does not handle DB2 sources — Snowflake only in this version
- Does not generate full-featured visual reports — the companion `.Report` folder is
  an intentional placeholder (single textbox page). Rich report authoring is the
  remit of `pbi-automation`

---

## Relationship to Other Tools

```
pbi-model-generator   →  generates .SemanticModel + .Report pairs  →  lpc-v1-app-ldi-pbi-mos
pbi-automation        →  generates full-featured .pbip reports      →  lpc-v1-app-ldi-pbi-mos
pbi-cli               →  validates DAX against running model
```

`pbi-automation` PBIP reports bind to the models generated by this tool via
`definition.pbir` `byPath` reference. The model name in `display_name` must match
exactly what `pbi-automation`'s `pbi.properties` `[model_keywords]` section references.

---

## Source Reference

Design based on research in `pbi-model-research/`:
- `research.md` — star schema architecture, column rules, partition strategy
- `generate_tmdl.py` — working prototype (fact table fragment generator)
- `output/*.tmdl` — 8 validated fact table fragments across 5 Snowflake schemas
