# RDL Report Spec: {Report Title}

<!--
  PAGINATED REPORT TEMPLATE — ODBC DATA SOURCE (.rdl)
  ─────────────────────────────────────────────────────────────────────────────
  Use this template when the report reads directly from the Awards/Resolution
  Database (ARDB) via an ODBC DSN rather than through a Snowflake or Power BI
  semantic model data source.

  WHEN TO USE THIS TEMPLATE vs. OTHER PAGINATED TEMPLATE
  ┌──────────────────────────────────┬─────────────────────────────────────────┐
  │ This template (ODBC)             │ Other paginated template (Snowflake/PBIP)│
  ├──────────────────────────────────┼─────────────────────────────────────────┤
  │ DataProvider = ODBC              │ DataProvider = PBIDATASET               │
  │ ConnectString = Dsn=MOS-Q1-ARDB  │ ConnectString = Data Source=pbiazure://…│
  │ Dataset query = SQL (ANSI)       │ Dataset query = DAX (EVALUATE …)        │
  │ Query params  = positional (?)   │ Query params  = named or DAX filters    │
  │ Source DB     = BOA_PS schema    │ Source model  = MO_Sales.pbip or similar│
  └──────────────────────────────────┴─────────────────────────────────────────┘

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
- **Sort:** {Default sort order, e.g. "Payment Date ASC then Check No. ASC" — or N/A}
- **Notes:** {Scheduling notes, special delivery requirements, or leave blank.}

---

## Data Source

<!--
  ODBC data sources reference a DSN configured on the Report Server.
  Do NOT use a shared .rds file — the connection is embedded in the .rdl.
  Current DSNs in use:
    MOS-Q1-ARDB  — Awards / Resolution Database (BOA_PS schema, Snowflake via ODBC)
-->

- **Name:** {DataSourceName}   *(e.g. ARDB)*
- **Provider:** ODBC
- **DSN:** `{DSN name}`   *(e.g. MOS-Q1-ARDB)*
- **Schema(s) used:** {e.g. BOA_PS, BOA_DICTIONARY — list all schemas queried in SQL}

---

## Parameters

<!--
  PARAMETER RULES (Section 2.1)
  • ExecDateTime is always present as a hidden String parameter; it is auto-populated
    at runtime with the current date/time and shown in the report header.
  • A label ending in * requires a value before the report can be run.
  • Single = user picks exactly one value.  Multiple = user picks one or more values.
  • ODBC datasets use positional (?) parameters; order in the table must match
    the order in which ? appears in the SQL WHERE clause.
-->

| # | Label | DataType | Single / Multiple | Required | Default / Notes |
|---|---|---|---|---|---|
| 1 | ExecDateTime | String | Single | — | Hidden — default `=Code.GetCST()` (embedded VB converts UTC→Central Standard Time) |
| 2 | Start Date | DateTime | Single | Yes (*) | Default: none |
| 3 | End Date | DateTime | Single | Yes (*) | Default: none |
| {n} | {Parameter Label} | {String \| DateTime \| Integer} | {Single \| Multiple} | {Yes \| No} | {Default value or "none"} |

<!--
  COMMON PARAMETER PATTERNS FOR ODBC REPORTS:
    ExecDateTime  String    Single    Hidden — run timestamp shown in header
    Start Date*   DateTime  Single    Default: none
    End Date*     DateTime  Single    Default: none
    (Add additional parameters if the SQL WHERE clause uses more filters)
-->

---

## Datasets

<!--
  ODBC reports typically have a single SQL dataset.
  Query parameters are positional (?), matched in the order they appear in SQL.
  The mapping below must list them in the same order as in the WHERE clause.
-->

### {DatasetName}   *(e.g. W2GReport)*

- **Data Source:** {DataSourceName}
- **Parameter mapping (positional):**

| Position | ? | Report Parameter |
|---|---|---|
| 1 | First `?` in SQL | `=Parameters!StartDate.Value` |
| 2 | Second `?` in SQL | `=Parameters!EndDate.Value` |
| {n} | n-th `?` | `=Parameters!{ParamName}.Value` |

- **Query:**

```sql
-- Replace with actual SQL.
-- Parameters are positional (?); order must match the mapping table above.
SELECT
    {column_alias_1},
    {column_alias_2},
    SUM({amount_column}) AS "{Aggregated Alias}"
FROM
    {schema}.{primary_table}
    LEFT OUTER JOIN {schema}.{lookup_table} ON {join_condition}
WHERE
    {date_column} BETWEEN ?  AND  ?
    AND {filter_column} NOT IN ({excluded_values})
GROUP BY
    {group_by_columns}
HAVING
    SUM({amount_column}) > {threshold}
```

- **Fields exposed to report:**

| Field Name | Source Column Alias | DataType | Notes |
|---|---|---|---|
| {FieldName} | "{Column Alias from SQL}" | {String \| Integer \| Decimal \| DateTime} | {raw \| calculated \| decrypted} |

<!--
  NOTE: Field names in RDL are derived from the SQL column aliases by replacing
  spaces and special characters with underscores.
  Example: "Payment Gross Amount" → Payment_Gross_Amount
  Decrypted fields use BOA_PS.DECRYPT_STRING(key, column) — mark as "decrypted".
-->

---

## Layout

<!--
  LAYOUT RULES (Section 2.1)
  • Column headers are displayed exactly as written in "Column Header".
  • "Field" maps to the dataset field name used in the textbox expression.
  • Totals rows appear at the bottom of the report (detail group only unless grouped).
  • <Layout Continued> in the FRD means the table continues — all columns belong
    to the same tab/table.

  EXPRESSION PATTERNS FOR ODBC FIELDS:
    Simple value:         =Fields!{FieldName}.Value
    Concatenated names:   =Trim(Fields!FirstName.Value & " " & Fields!LastName.Value)
    Count (footer):       =Count(Fields!{FieldName}.Value)
    Sum (footer):         =Sum(Fields!{FieldName}.Value)
-->

### Tab 1: {Tab Name}   *(remove heading if report has only one tab)*

- **Grouping:** {Details only (no grouping) | e.g. "by Payment Date ascending"}
- **Totals row:** {Yes — Count of [{col}], Sum of [{col1}, {col2}] / No}

| Column Header | Field | Expression | DataType | Format | Alignment |
|---|---|---|---|---|---|
| {Column 1 Header} | {FieldName1} | `=Fields!{FieldName1}.Value` | String | as-stored | Center |
| {Column 2 Header} | {FieldName2} | `=Fields!{FieldName2}.Value` | Decimal | $0,000.00 / ($0,000.00) | Right |
| {Column 3 Header} | {FieldName3} | `=Fields!{FieldName3}.Value` | DateTime | MM/DD/YYYY | Center |
| {Column 4 Header} | {FieldName4} | `=Trim(Fields!A.Value & " " & Fields!B.Value)` | String | — | Left |

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
  └───────────────────────────────┴──────────────────────────────────────┴───────────┘
-->

---

## Business Rules / Requirements

<!--
  List every "The report shall…" statement from the FRD Requirements section.
  Each bullet = one atomic business rule.
  For calculated fields, write the formula using (+) (−) notation as in the FRD.
-->

- The report shall include data only for payments paid within the specified date or date range.
- The report shall {describe additional filter / inclusion / exclusion criteria}.
- The report shall define **{CalculatedField}** as {Expression using (+) (−) notation}.
- The report shall cite the count of {items} and the total {amounts} across all {items}.
- {Add additional requirements as needed.}

---

## Header / Footer

<!--
  ODBC paginated reports use this standard header layout (confirmed from W2G Report.rdl):
    Left   : Missouri Lottery logo
    Centre : Report title
    Right  : "Run Datetime: {ExecDateTime}"  /  "Date Range: {StartDate} - {EndDate}"
  Footer:
    Left   : Report name (=Globals!ReportName)
    Right  : "Page {PageNumber}"
  
  List the parameter labels that appear in the header right-hand panel.
-->

- **Report Header (left):** Missouri Lottery logo
- **Report Header (centre):** `{Report Title}`
- **Report Header (right, line 1):** `Run Datetime: {ExecDateTime}`
- **Report Header (right, line 2):** `Date Range: {StartDate} - {EndDate}`
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
