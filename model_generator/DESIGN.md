# pbi-automation / model_generator — Design Document

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
python generate_models.py                             # generate all [model.*] sections
python generate_models.py --model financial_daily     # generate one model only
python generate_models.py --list                      # list all configured models
python generate_models.py --env d1v1                  # target a specific environment
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
> `py generate_models.py ...`

### `[snowflake.<env>]` — per-environment overrides

Any key in a `[snowflake.<env>]` section overrides the matching key from `[snowflake]`.
Unspecified keys fall back to the base section.

```ini
[snowflake.d1v1]
account   = igtgloballottery-igtd2v1_ldi.privatelink
warehouse = LPCDXV1_WH_LDI
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
suffixes can be added at any time without code changes.

### `[dimensions]` — conformed dimension table declarations

```ini
[dimensions]
dates      = DIMCORE.DATES,     primary_key=DATE_KEY,     strategy=A
products   = DIMCORE.PRODUCTS,  primary_key=PRODUCT_KEY,  strategy=A
locations  = DIMCORE.LOCATIONS, primary_key=LOCATION_KEY, strategy=A
terminals  = DIMCORE.TERMINALS, primary_key=TERMINAL_KEY, strategy=A
```

Each dimension entry declares:
- The Snowflake source table (`SCHEMA.TABLE`)
- The primary key column used for the join (`primary_key`)
- The column visibility strategy (`strategy`, default: `A`)
- Optionally, `inherit=<alias>` for role-playing dimensions (see below)

### `[model.*]` — one section per semantic model

```ini
[model.financial_daily]
display_name = Financial Daily LDI
fact_table   = FINANCIAL.FINANCIAL_DAILY
dimensions   = dates, products, locations, terminals

[model.draw_sales]
display_name  = Draw Sales LDI
fact_table    = DRAW.DRAW_SALES
dimensions    = dates, products, locations
filter_column = BUSINESS_TIMESTAMP    # optional — adds RangeStart/RangeEnd incremental refresh params
```

`display_name` becomes the Power BI model name and folder name. It must follow the
handbook naming standard: Title Case + mandatory postfix (LDI / RSM / RPT).

`filter_column` is optional. When set, a `Table.SelectRows` filter step is inserted
into the fact table's M query (`[COLUMN] >= RangeStart and [COLUMN] < RangeEnd`),
and `RangeStart` / `RangeEnd` DateTime parameters are added to `expressions.tmdl`
for incremental refresh configuration.

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
#  → expands Products using GAME_PRODUCT_KEY as the fact-side join column
```

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

Each alias produces an independent TMDL staging table with its own display name
(`Dates First Val`, `Dates Last Val`) and its own NestedJoin step in the fact M
query, while reading column visibility from the shared `model_generator/dimensions/dates.yaml`.

---

## Star Schema Architecture — Merged Queries

The model uses **Power Query merged queries** instead of TMDL relationships. This
approach is required for compatibility with `.rdl` paginated reports, which cannot
consume models that rely on in-model relationships.

Each dimension table is generated as a hidden staging table in Import mode. The fact
table's M partition chains a `Table.NestedJoin` + `Table.ExpandTableColumn` step for
each dimension, pulling all selected dimension columns directly into the fact table's
flat column list.

```
Fact M query:
  Source → DB → Schema → FactTable
    → [Optional] Filtered Rows          (if filter_column is set)
    → Merged Dates  → Expanded Dates
    → Merged Products → Expanded Products
    → Merged Locations → Expanded Locations
    → ...
```

No `relationships.tmdl` is generated.

### Fact Table Column Classification

The tool connects to Snowflake and runs `SHOW COLUMNS IN TABLE <schema>.<table>` to
retrieve the full column list. Rules are applied in priority order:

| Column pattern | TMDL output | Notes |
|---|---|---|
| Name ends with `_KEY` | Hidden, `dataType: int64`, `summarizeBy: none` | Identifies all join keys; no measure generated |
| Ends in `_COUNT` (configurable) | Hidden source column + `CALCULATE(SUM(...))` measure | `format: "0"`, folder `Base Measures` |
| Ends in `_AMOUNT` (configurable) | Hidden source column + `CALCULATE(SUM(...))` measure | `format: "#,##0.00"`, folder `Base Measures` |
| Ends in `_QUANTITY` (configurable) | Hidden source column + `CALCULATE(SUM(...))` measure | `format: "#,##0"`, folder `Base Measures` |
| Anything else | Visible column, `summarizeBy: none` | No display folder (root of field pane) |

### Dimension Column Display

Dimension columns expanded into the fact table are grouped in the field pane under a
display folder named after the dimension alias in Title Case (e.g. `Dates`, `Products`,
`Locations`).

### Cross-Dimension Name Collision Resolution

If two dimensions expose a column with the same display name (e.g. both Products and
Locations define `SETTLE_CLASS_CODE → "Settle Class Code"`), the generator
automatically prefixes every colliding name with the dimension's table name:

```
Products dim  → "Products Settle Class Code"
Locations dim → "Locations Settle Class Code"
```

This applies consistently to both the M query `ExpandTableColumn` output names and
the TMDL column declarations, so no manual intervention is needed.

### Measure Naming

Source column name → measure name: split on `_`, capitalise each word.

```
SALES_COUNT                        →  Sales Count
VALIDATION_BASED_SALES_AMOUNT      →  Validation Based Sales Amount
```

All base measures go into `displayFolder: "Base Measures"`. Derived measures (YTD,
PY, ratios) are authored manually in Tabular Editor after the base model is deployed.

---

## Dimension Column Visibility Strategies

### Strategy A — Config-driven (default)

You explicitly list which columns should be visible in a YAML file at
`model_generator/dimensions/<alias>.yaml`. Every column not in that list is hidden
in the staging table. The right-hand value is the business display name that appears
when the column is expanded into the fact table.

```yaml
# model_generator/dimensions/dates.yaml
visible_columns:
  CALENDAR_DAY_DATE:     Date
  CALENDAR_YEAR_STRING:  Calendar Year
  FISCAL_YEAR_STRING:    Fiscal Year
  FISCAL_MONTH_STRING:   Fiscal Month
```

If the YAML file is missing, the tool warns and hides all dimension columns (no
columns are expanded into the fact table for that dimension). Role-playing aliases
with `inherit=<alias>` reuse the parent's YAML — no duplication needed.

**When to use:** All `DIMCORE` dimensions and any dimension where you want precise
control over what report authors see.

### Strategy B — Snowflake introspection

The tool retrieves the full column list from Snowflake at runtime and automatically
expands all columns except the primary key, deriving display names via
`SNAKE_CASE → Title Case` conversion.

No YAML file required.

**When to use:** Dimensions that are large and you want full auto-discovery, or when
the Snowflake source already uses business-friendly column names. For `DIMCORE`
tables (which are ALL_UPPERCASE throughout), Strategy A is strongly preferred — you
typically do not want every technical column visible.

---

## Output Structure

Each model generates a matched pair of folders under `output/models/`:

```
output/models/
├── Financial Daily LDI.SemanticModel/
│   ├── .platform                         ← Fabric metadata (type, displayName, logicalId GUID)
│   ├── definition.pbism                  ← PBISM version manifest
│   └── definition/
│       ├── database.tmdl                 ← compatibilityLevel: 1600
│       ├── model.tmdl                    ← culture, ref tables
│       ├── expressions.tmdl             ← Snowflake connection parameters (+ RangeStart/RangeEnd if filter_column set)
│       └── tables/
│           ├── Financial Daily.tmdl     ← fact table (import mode): key cols + measures + dimension cols
│           ├── Dates.tmdl               ← staging table (hidden, import mode)
│           ├── Products.tmdl
│           ├── Locations.tmdl
│           └── Terminals.tmdl
│
└── Financial Daily LDI.Report/
    ├── .platform                         ← Fabric metadata (type: Report, logicalId GUID)
    ├── definition.pbir                   ← byPath reference to sibling .SemanticModel
    ├── .pbi/
    │   └── localSettings.json
    └── definition/
        ├── report.json                   ← CY24SU10 theme, report-level settings
        ├── version.json
        ├── pages/
        │   └── <pageId>/
        │       └── visuals/<visualId>/
        │           └── visual.json       ← single textbox: "intentionally left blank"
        └── StaticResources/
            └── SharedResources/
                └── BaseThemes/
                    └── CY24SU10.json     ← copied from model_generator/templates/BaseThemes/
```

Note: no `relationships.tmdl` — all joins are handled by the fact table's M query.

Both folders in a pair are committed and deployed together to `lpc-v1-app-ldi-pbi-mos`.
The `.Report` folder's `definition.pbir` uses a relative `byPath` reference to bind to
its sibling `.SemanticModel`, so the pair must always be in the same parent directory.

### `expressions.tmdl` parameters

```tmdl
expression SnowflakeServer    = "igtgloballottery-igtpxv1_ldi.snowflakecomputing.com" ...
expression SnowflakeWarehouse = "lpcdxv1_wh_ldi" ...
expression SnowflakeRole      = "mosq1v1_ru_datareader" ...
expression SnowflakeDBName    = "MOSQ1V1_DB_DH" ...

# Added when filter_column is set on a model:
expression RangeStart = #datetime(2020, 1, 1, 0, 0, 0) meta [Type="DateTime", ...]
expression RangeEnd   = #datetime(2030, 1, 1, 0, 0, 0) meta [Type="DateTime", ...]
```

The server hostname is built as `{account}.snowflakecomputing.com` from the config
value. For privatelink accounts (e.g. d1v1), the `.privatelink` suffix is already
part of the `account` value, producing the correct hostname automatically.

---

## Multi-Environment Support

```bash
python generate_models.py --env d1v1    # development (privatelink)
python generate_models.py --env c1v1    # certification / UAT
python generate_models.py --env p1v1    # production
```

Environment-specific values override the base `[snowflake]` section for the current
run. The generated `expressions.tmdl` contains the env-specific server and warehouse
values. Running without `--env` uses the base `[snowflake]` section.

---

## Handbook Compliance

All generated artifacts comply with the Power BI Developer Handbook & Guide:

| Handbook rule | How enforced |
|---|---|
| Semantic model names: Title Case + postfix (LDI/RSM/RPT) | `display_name` in `[model.*]` |
| User-facing objects: Title Case, no technical prefixes | Measure names converted from SNAKE_CASE automatically |
| Hidden technical objects: `summarizeBy: none` | Applied to all hidden source columns |
| Snowflake native connector (ADBC 2.0) | M query uses `Snowflake.Databases(..., [Implementation="2.0"])` |
| Connection parameters in `expressions.tmdl` | Never hardcoded — always from config |
| PBIP/TMDL format only | Output is TMDL — no `.pbix` generated |

---

## How To

### Add a new semantic model

1. Add a `[model.*]` section to `semantic.properties`:

   ```ini
   [model.my_model]
   display_name = My Model LDI
   fact_table   = SCHEMA.FACT_TABLE
   dimensions   = dates, products, locations
   ```

   `display_name` must end with `LDI`, `RSM`, or `RPT` (handbook requirement).

2. Optionally add `filter_column` for incremental refresh:

   ```ini
   filter_column = BUSINESS_TIMESTAMP
   ```

   This adds `RangeStart` / `RangeEnd` parameters to `expressions.tmdl` and a `Table.SelectRows` step in the fact M query.

3. Generate:

   ```bash
   python generate_models.py --model my_model
   ```

---

### Add a new dimension

1. Register in `[dimensions]`:

   ```ini
   draw_information = DRAW.DRAW_INFORMATION, primary_key=DRAW_INFO_KEY, strategy=A
   ```

2. For `strategy=A`, create `model_generator/dimensions/draw_information.yaml`:

   ```yaml
   visible_columns:
     DRAW_NUMBER:      Draw Number
     DRAW_DATE:        Draw Date
     DRAW_DESCRIPTION: Draw Description
   ```

   Only listed columns are expanded into the fact table. Omit the file for `strategy=B` (all non-key columns auto-expanded).

3. Add the alias to the model's `dimensions` list:

   ```ini
   dimensions = dates, products, draw_information
   ```

   Non-standard fact join key: `draw_information:FACT_DRAW_KEY`

4. Regenerate the model.

---

### Add a new measure suffix

Edit `[measure_suffixes]` in `semantic.properties` — no code changes required:

```ini
[measure_suffixes]
_COUNT    = int64,   0
_AMOUNT   = decimal, #,##0.00
_QUANTITY = int64,   #,##0
_WEIGHT   = decimal, #,##0.000   # ← new
```

Any fact column ending `_WEIGHT` will produce a hidden source column and a `CALCULATE(SUM(...))` measure in the **Base Measures** display folder.

---

### Target a specific environment

```bash
python generate_models.py --env d1v1   # development (privatelink account)
python generate_models.py --env c1v1   # certification / UAT
python generate_models.py --env p1v1   # production
```

Per-environment values in `[snowflake.<env>]` override the base `[snowflake]` section for that run. The generated `expressions.tmdl` contains the env-specific server and warehouse.

---

### Use a role-playing dimension

When a fact table joins the same physical table twice (e.g. two date keys), declare each join as a separate alias using `inherit=<parent>` to share the YAML:

```ini
[dimensions]
dates           = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A
dates_draw      = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A, inherit=dates
dates_settle    = DIMCORE.DATES, primary_key=DATE_KEY, strategy=A, inherit=dates
```

Reference both aliases with their respective fact columns:

```ini
dimensions = dates, dates_draw:DRAW_DATE_KEY, dates_settle:SETTLE_DATE_KEY, products
```

Each alias produces an independent M staging table (`Dates Draw`, `Dates Settle`) and its own display folder in the field pane.

---

## What This Tool Does Not Do

- Does not generate derived measures (YTD, PY, ratios, KPIs) — those are authored
  manually in Tabular Editor after the base model is deployed
- Does not generate RLS roles
- Does not deploy to Fabric — output is files for Git commit and CI/CD pipeline
- Does not handle DB2 sources — Snowflake only
- Does not generate full-featured visual reports — the companion `.Report` folder is
  an intentional placeholder (single textbox page)

---

## Relationship to Other Tools

```
model_generator   →  generates .SemanticModel + .Report pairs  →  lpc-v1-app-ldi-pbi-mos
report_generator  →  generates full-featured .rdl / .pbip reports  →  lpc-v1-app-ldi-pbi-mos
pbi-cli           →  validates DAX against running model
```

`report_generator` PBIP reports bind to the models generated by this tool via
`definition.pbir` `byPath` reference. The model name in `display_name` must match
exactly what `pbi-automation`'s `pbi.properties` `[model_keywords]` section references.
