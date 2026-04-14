# RDL Report Spec: {Report Title}

<!--
  PAGINATED REPORT TEMPLATE — SNOWFLAKE ODBC DATA SOURCE (.rdl)
  ─────────────────────────────────────────────────────────────────────────────
  Use this template when the report connects directly to Snowflake via an ODBC
  DSN (MOS-PX-SFODBC) rather than through the ARDB/BOA_PS database or a Power
  BI semantic model.

  WHEN TO USE THIS TEMPLATE vs. OTHER PAGINATED TEMPLATES
  ┌──────────────────────────────────────┬──────────────────────────────────────┐
  │ This template (Snowflake ODBC)       │ Other paginated — ARDB ODBC          │
  ├──────────────────────────────────────┼──────────────────────────────────────┤
  │ DataProvider = ODBC                  │ DataProvider = ODBC                  │
  │ ConnectString = Dsn=MOS-PX-SFODBC   │ ConnectString = Dsn=MOS-Q1-ARDB      │
  │ Schemas = TXNDTL, DIMCORE, FINANCIAL │ Schema = BOA_PS                      │
  │ Date params → Format(…,"yyyy-MM-dd") │ No special date formatting needed    │
  │ Multi-value → JOIN(…,",")           │ Multi-value → JOIN(…,",")            │
  │ Multi-value SQL → SPLIT_TO_TABLE    │ Multi-value SQL → SPLIT_TO_TABLE     │
  │ No ExecDateTime / GetCST() VB code  │ ExecDateTime hidden param + VB code  │
  │ No DECRYPT_STRING                   │ DECRYPT_STRING for sensitive columns  │
  └──────────────────────────────────────┴──────────────────────────────────────┘

  HOW TO USE
  1. Replace every {Placeholder} with the actual value.
  2. Fill in Parameters, Datasets (SQL), Layout, and Business Rules.
  3. Copilot will use this file to generate the .rdl XML file.

  SECTION 2.1 REQUIREMENTS (apply to ALL paginated reports automatically)
    • Header  : Report title + parameter values + run date/time (MM/DD/YYYY HH:MM:SS)
    • Footer  : Report name + Page X of Y
    • Logo    : Missouri Lottery logo, top-left corner of header
    • Data    : see "General Formatting" section at the bottom
-->

---

## Metadata

- **Report Title:** {Report Title}
- **Legacy Path:** `{01. Public Folders\Missouri\...\Legacy Report Name}`
- **Legacy Users:** {Brightstar | Lottery Accounting | Lottery Sales | Lottery Marketing | …}
- **Description:** {One-sentence description of what the report shows and its primary audience.}
- **Report Format:** Paginated (.rdl)
- **Output Folder:** {Reports - Brightstar | Reports - Lottery Accounting | …}
- **Page Orientation:** {Landscape (11in × 8.5in) | Portrait (8.5in × 11in)}
- **Sort:** {Default sort order, e.g. "TXN_DATE ASC then TXN_TIME ASC" — or N/A}
- **Notes:** {Scheduling notes, special delivery requirements, or leave blank.}

---

## Data Source

<!--
  The connection is embedded directly in the .rdl (no shared .rds file).
  DSN must be configured on the Report Server / Fabric gateway.
  Common Snowflake schemas in use:
    TXNDTL   — transaction detail (MAIN_TXN, PROMOTION, INSTANT_VALIDATION, DRAW_WAGER …)
    DIMCORE  — dimension / reference tables (DATES, PRODUCTS, CODES, LOCATIONS …)
    FINANCIAL — financial summary tables
-->

- **Name:** `LPC_E2_SFODBC`   *(or a report-specific alias — match the Name attribute in the .rdl)*
- **Provider:** ODBC
- **DSN:** `MOS-PX-SFODBC`
- **Schema(s) used:** {e.g. TXNDTL, DIMCORE — list all schemas queried across all datasets}

---

## Parameters

<!--
  PARAMETER RULES (Section 2.1)
  • A label ending in * requires a value before the report can be run.
  • Single = user picks exactly one value.  Multiple = user picks one or more values.
  • There is NO ExecDateTime / GetCST() hidden parameter on Snowflake ODBC reports.
  • Query parameter mapping is POSITIONAL — the order of rows below must match the
    order in which ? appears across the SQL WHERE clause (see Datasets section).

  DATE PARAMETER EXPRESSION (required for Snowflake compatibility):
    =Format(Parameters!{paramName}.Value, "yyyy-MM-dd")
    Snowflake expects ISO-8601 date strings; without this format the cast ?::DATE fails.

  MULTI-VALUE PARAMETER EXPRESSION:
    =JOIN(Parameters!{paramName}.Value, ",")
    This produces a comma-separated string passed to SPLIT_TO_TABLE in SQL.
-->

| # | Label | DataType | Single / Multiple | Required | Query expression |
|---|---|---|---|---|---|
| 1 | Start Date | DateTime | Single | Yes (*) | `=Format(Parameters!startDate.Value, "yyyy-MM-dd")` |
| 2 | End Date | DateTime | Single | Yes (*) | `=Format(Parameters!endDate.Value, "yyyy-MM-dd")` |
| {n} | {Parameter Label} | {String \| Integer \| DateTime} | {Single} | {Yes \| No} | `=Format(Parameters!{paramName}.Value, "yyyy-MM-dd")` |
| {n} | {Parameter Label} | {String \| Integer} | Multiple | {Yes \| No} | `=JOIN(Parameters!{paramName}.Value, ",")` |

<!--
  COMMON PARAMETER PATTERNS FOR SNOWFLAKE ODBC REPORTS:
    Start Date*        DateTime  Single    =Format(…, "yyyy-MM-dd")
    End Date*          DateTime  Single    =Format(…, "yyyy-MM-dd")
    Product Number     Integer   Multiple  =JOIN(…, ",") → SPLIT_TO_TABLE in SQL
    Transaction Type   String    Multiple  =JOIN(…, ",") → SPLIT_TO_TABLE in SQL
    Retailer No.*      Integer   Single    =Parameters!retailerNo.Value
    Terminal No.       Integer   Multiple  =JOIN(…, ",") → SPLIT_TO_TABLE in SQL
-->

---

## Datasets

<!--
  DATASET RULES FOR SNOWFLAKE ODBC REPORTS:
  • Query parameters are POSITIONAL (Name="?" in QueryParameters).
  • The order of <QueryParameter> elements must match the order of ? in the SQL.
  • Date range — use a date-key subquery (Snowflake stores integer date keys):
      (SELECT date_key FROM dimcore.dates WHERE calendar_day_date = ? :: DATE)
  • Multi-value IN filter — use SPLIT_TO_TABLE:
      Integer column:  IN (SELECT t.VALUE::number FROM TABLE(SPLIT_TO_TABLE(?, ',')) t)
      String column:   IN (SELECT t.VALUE        FROM TABLE(SPLIT_TO_TABLE(?, ',')) t)
  • Lookup datasets (for parameter dropdowns) query DIMCORE reference tables.
-->

### ds_Main   *(rename if the .rdl uses a different name, e.g. DataSet1)*

- **Data Source:** `LPC_E2_SFODBC`
- **Query parameter mapping (positional):**

| Position | `?` | Report parameter expression |
|---|---|---|
| 1 | First `?` in SQL | `=Format(Parameters!startDate.Value, "yyyy-MM-dd")` |
| 2 | Second `?` in SQL | `=Format(Parameters!endDate.Value, "yyyy-MM-dd")` |
| {n} | n-th `?` | `=JOIN(Parameters!{paramName}.Value, ",")` |

- **Query:**

```sql
-- Replace with actual SQL.
-- Parameters are positional (?); order must match the mapping table above.
-- Date range filter via DIMCORE.DATES date-key lookup:
SELECT
    {col_alias_1},
    {col_alias_2},
    TO_CHAR({amount_column}, '$999,999,999,990.00') AS "{Amount Alias}"
FROM
    TXNDTL.{primary_table} t
    LEFT OUTER JOIN TXNDTL.{related_table} r
        ON  t.DATE_KEY       = r.DATE_KEY
        AND t.SERIAL_NUMBER  = r.SERIAL_NUMBER
        AND t.PRODUCT_NUMBER = r.PRODUCT_NUMBER
WHERE
    t.DATE_KEY >= (SELECT date_key FROM DIMCORE.DATES WHERE calendar_day_date = ? :: DATE)
    AND t.DATE_KEY <= (SELECT date_key FROM DIMCORE.DATES WHERE calendar_day_date = ? :: DATE)
    -- Integer multi-value:
    AND t.{int_column}    IN (SELECT val.VALUE::number FROM TABLE(SPLIT_TO_TABLE(?, ',')) val)
    -- String multi-value:
    AND t.{string_column} IN (SELECT val.VALUE        FROM TABLE(SPLIT_TO_TABLE(?, ',')) val)
ORDER BY
    {default_sort_columns}
```

- **Fields exposed to report:**

| Field Name | Source Column Alias | DataType | Notes |
|---|---|---|---|
| {FieldName} | `{COLUMN_ALIAS}` | {String \| Integer \| Decimal \| DateTime} | {raw \| pre-formatted by TO_CHAR} |

<!--
  NOTE: Snowflake ODBC reports sometimes pre-format currency in SQL using TO_CHAR
  (e.g. TO_CHAR(TXN_AMOUNT, '$999,999,999,990.00') AS Transaction_Amount).
  In that case treat the field as String in RDL — do not apply a format string.
  For amounts returned as raw Decimal, apply $0,000.00 / ($0,000.00) in the layout.
-->

### ds_{LookupName}   *(one section per lookup dataset — remove if not needed)*

- **Purpose:** Populate the `{ParameterLabel}` parameter dropdown
- **Data Source:** `LPC_E2_SFODBC`
- **Query:**

```sql
-- Lookup datasets typically query DIMCORE reference tables.
SELECT {code_column}, {label_column}
FROM DIMCORE.{reference_table}
WHERE {filter_condition}
ORDER BY {label_column}
```

- **DataSetReference in parameter:** `DataSetName={ds_LookupName}`, `ValueField={code_column}`, `LabelField={label_column}`

---

## Layout

<!--
  LAYOUT RULES (Section 2.1)
  • Column headers are displayed exactly as written in "Column Header".
  • "Field" maps to the dataset field name used in the textbox expression.
  • Totals rows appear at the bottom of the report (or at each group boundary).
  • <Layout Continued> in the FRD means the table continues — all columns belong
    to the same tab/table.

  EXPRESSION PATTERNS FOR SNOWFLAKE ODBC FIELDS:
    Simple value:         =Fields!{FieldName}.Value
    Concatenated names:   =Trim(Fields!FirstName.Value & " " & Fields!LastName.Value)
    Count (footer):       =Count(Fields!{FieldName}.Value)
    Sum (footer):         =Sum(Fields!{FieldName}.Value)

  NOTE: Fields pre-formatted by TO_CHAR in SQL (returned as String) should use
  expression =Fields!{FieldName}.Value with no additional format string.
-->

### Tab 1: {Tab Name}   *(remove heading if report has only one tab)*

- **Grouping:** {Details only (no grouping) | e.g. "by Retailer ID ascending, then Date ascending"}
- **Totals row:** {Yes — Count of [{col}], Sum of [{col1}, {col2}] / No}

| Column Header | Field | Expression | DataType | Format | Alignment |
|---|---|---|---|---|---|
| {Column 1 Header} | {FieldName1} | `=Fields!{FieldName1}.Value` | String | as-stored | Center |
| {Column 2 Header} | {FieldName2} | `=Fields!{FieldName2}.Value` | Decimal | $0,000.00 / ($0,000.00) | Right |
| {Column 3 Header} | {FieldName3} | `=Fields!{FieldName3}.Value` | DateTime | MM/DD/YYYY | Center |
| {Column 4 Header} | {FieldName4} | `=Fields!{FieldName4}.Value` | String | pre-formatted (TO_CHAR) | Right |

<!--
  FORMAT REFERENCE (from Section 2.1):
  ┌───────────────────────────────┬──────────────────────────────────────┬───────────┐
  │ Data type                     │ Format string                        │ Alignment │
  ├───────────────────────────────┼──────────────────────────────────────┼───────────┤
  │ Currency / sales amounts      │ $0,000.00 / ($0,000.00) / $0.00      │ Right     │
  │ Counts / non-currency numbers │ 0,000 / (0,000) / 0                  │ Right     │
  │ Date                          │ MM/DD/YYYY                           │ Center    │
  │ Time                          │ HH:MM:SS  (24-hour)                  │ Center    │
  │ Phone number                  │ 123-456-7890                         │ Center    │
  │ Code / ID / Type / Zip        │ as-stored                            │ Center    │
  │ Name / Address / Text         │ —  (no special format)               │ Left      │
  │ Pre-formatted by TO_CHAR      │ —  (return as String, no RDL format) │ Right     │
  └───────────────────────────────┴──────────────────────────────────────┴───────────┘
-->

---

## Business Rules / Requirements

<!--
  List every "The report shall…" statement from the FRD Requirements section.
  Each bullet = one atomic business rule.
  For calculated fields, write the formula using (+) (−) notation as in the FRD.
-->

- The report shall include data only for transactions occurring within the specified date range.
- The report shall filter by {parameter} when provided.
- The report shall define **{CalculatedField}** as {Expression using (+) (−) notation}.
- The report shall cite the count of {items} and the total {amounts} across all {items}.
- {Add additional requirements as needed.}

---

## Header / Footer

<!--
  Snowflake ODBC paginated reports use this standard header layout.
  There is no ExecDateTime / GetCST() VB function — use the standard run-time
  expression =Globals!ExecutionTime (rendered as MM/DD/YYYY HH:MM:SS in local time).
  List the parameter labels that appear in the header right-hand panel.
-->

- **Report Header (left):** Missouri Lottery logo
- **Report Header (centre):** `{Report Title}`
- **Report Header (right, line 1):** `Start Date: {startDate}`
- **Report Header (right, line 2):** `End Date: {endDate}`
- **Report Header (right, line 3):** `{Additional parameter label}: {paramValue}`  *(if applicable)*
- **Report Footer (left):** `=Globals!ReportName`
- **Report Footer (right):** `Page [&OverallPageNumber] of [&OverallTotalPages]`

---

## General Formatting  *(Section 2.1 — applies to all reports)*

- Any access restrictions to reports will be managed through assigned Security roles.
- The field length of all column and row values extracted from the database will be
  accommodated to their full lengths; formats will be retained unless specified otherwise.
- The header shall cite the defined parameters and the run date and time of the report output.
- The report footer shall cite the report name and output page.

**Data formats:**

- Date: `MM/DD/YYYY`
- Time: `HH:MM:SS` (24-hour)
- Currency: `$0,000.00` · negatives: `($0,000.00)` · zeros: `$0.00`
- Counts: `0,000` · negatives: `(0,000)` · zeros: `0`
- Phone: `123-456-7890`
- Codes / numbers: formatted as stored unless otherwise specified
- Right-justified: all currency and non-currency numeric columns
- Centered: dates, codes, IDs, phone numbers
- Left-justified: names, addresses, and all other alphanumeric values
