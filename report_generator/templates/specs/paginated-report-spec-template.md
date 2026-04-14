# RDL Report Spec: {Report Title}

<!--
  PAGINATED REPORT TEMPLATE (.rdl)
  ─────────────────────────────────────────────────────────────────────────────
  Use this template to document a Performance Wizard PAGINATED report.
  Paginated reports produce a single tabular visualisation that can be:
    • Viewed on-screen in Performance Wizard
    • Printed or exported to PDF / Excel
    • Scheduled and emailed as an attachment
  Output format: SSRS / Power BI Report Builder  (.rdl XML)

  HOW TO USE
  1. Replace every {Placeholder} with the actual value from the FRD.
  2. Fill in the Parameters, Layout, and Business Rules sections.
  3. Supply the SQL query in the Datasets section (or mark as TBD).
  4. Copilot will use this file to generate the .rdl XML file.

  SECTION 2.1 REQUIREMENTS (apply to ALL paginated reports automatically)
    • Header  : Report title + parameter values + run date/time (MM/DD/YYYY HH:MM:SS)
    • Footer  : Report title + Page X of Y
    • Logo    : Missouri Lottery logo, top-left corner of header
    • Data    : see "General Formatting" section at the bottom
-->

---

## Metadata

- **Report Title:** {Report Title}
- **Legacy Path:** `{01. Public Folders\Missouri\...\Legacy Report Name}`
- **Legacy Users:** {Brightstar | Lottery Sales | Lottery Marketing | …}
- **Description:** {One-sentence description of what the report shows and its primary audience.}
- **Report Format:** Paginated (.rdl)
- **Output Folder:** {Reports - Brightstar | Reports - Lottery Sales | …}
- **Sort:** {Default sort order, e.g. "Retailer No. ASC then Date ASC" — or N/A}
- **Notes:** {Scheduling notes, special delivery requirements, or leave blank.}

---

## Data Source

<!--
  SEMANTIC MODEL (most paginated reports)
  Replace {WorkspaceSlug}, {ModelName}, {tenant-id}, and {dataset-guid} with real values.
  WorkspaceSlug = workspace_name with spaces and dashes removed  (e.g. MissouriD1V1)
  ModelName     = the MO_* dataset used by this report            (e.g. MO_Sales)
  GUIDs are in the Fabric workspace URL or in pbi.properties [datasets].
-->

- **Name:** `{WorkspaceSlug}_{ModelName}`  *(e.g. `MissouriD1V1_MO_Sales`)*
- **Provider:** `PBIDATASET`
- **Connection string:**
  ```
  Data Source=pbiazure://api.powerbi.com/;
  Identity Provider="https://login.microsoftonline.com/organizations,
    https://analysis.windows.net/powerbi/api,
    {tenant-id}";
  Initial Catalog=sobe_wowvirtualserver-{dataset-guid};
  Integrated Security=ClaimsToken
  ```
- **Semantic model:** `{ModelName}.SemanticModel` (dataset GUID: `{dataset-guid}`)
- **Table used:** `{Table name from the semantic model}`

> **Note:** Parameters are applied via Power BI service parameter binding — they are **not** passed as explicit query parameters in the DAX `EVALUATE` statement. The semantic model filters the data based on the bound parameter values before the query executes.

---

## Parameters

<!--
  PARAMETER RULES (Section 2.1)
  • A label ending in * requires a value before the report can be run.
  • Single = user picks exactly one value.
  • Multiple = user can pick one or more values (multi-value parameter).
  • Parameters appear in the report header automatically.
-->

| Label | Single / Multiple | Default / Notes |
|---|---|---|
| {Parameter Label 1}* | Single | Default: {value or "none"} |
| {Parameter Label 2}* | Multiple | Default: All |
| {Parameter Label 3} | Single | Default: {value — optional parameter, no *} |

<!--
  COMMON PARAMETER PATTERNS SEEN IN THIS FRD:
    Start Date*        Single     Default: Current date − 1
    End Date*          Single     Default: Current date − 1
    Chain No. - Name*  Multiple   Default: All
    Retailer No. - Name* Multiple Default: All
    Terminal Type*     Multiple   Default: All
    Game Name          Multiple   Default: All
    Region             Multiple   Default: All
-->

---

## Datasets

<!--
  Provide one dataset per logical query. Most reports need only ds_Main.
  Add lookup datasets (ds_Chains, ds_Games, etc.) if parameters need
  a dynamic dropdown populated from a separate query.
-->

### ds_Main

- **Parameters used:** {comma-separated list, e.g. @StartDate, @EndDate, @ChainNo}
- **Snowflake schemas:** {e.g. financial, dimcore}
- **Query:**

```sql
-- TODO: Replace with actual SQL
SELECT
    {column_list}
FROM
    {schema}.{table_name} t
    JOIN {schema}.{dim_table} d ON t.{key} = d.{key}
WHERE
    t.sale_date BETWEEN @StartDate AND @EndDate
    -- Add additional filter conditions for each parameter
ORDER BY
    {default_sort_columns}
```

- **Fields exposed to report:**

| Field Name | Source Column | DataType | Notes |
|---|---|---|---|
| {FieldName} | {schema.table.column} | {String \| Integer \| Decimal \| DateTime} | {e.g. calculated, or "raw"} |

<!--
  ADD CALCULATED FIELDS HERE if they are computed in the dataset (not in report expressions):
  Example:
  | DrawGameSales | GROSS_SALES - CANCELS - FREE_TICKETS - DISCOUNTS - CASHLESS_SALES - DGAG | Decimal | |
-->

### ds_{LookupName}  *(if needed — remove if not used)*

- **Purpose:** Populate the `{ParameterLabel}` parameter dropdown
- **Query:**

```sql
SELECT DISTINCT {code_column}, {name_column}
FROM {schema}.{table}
ORDER BY {name_column}
```

---

## Layout

<!--
  LAYOUT RULES (Section 2.1)
  • Column headers are displayed exactly as written in "Column Header".
  • "Field" maps to the ds_Main field name used in the textbox expression.
  • Totals rows appear at the bottom of every grouping level listed.
  • <Layout Continued> in the FRD means the table continues — all columns
    belong to the same tab/table.

  ADD ONE "### Tab N" SECTION PER REPORT TAB.
  If the report has only one tab, omit the tab heading.
-->

### Tab 1: {Tab Name}

- **Grouping:** {e.g. RetailerNo → TerminalID → SaleDate (ascending)}
- **Totals row:** {Yes — sum [col1, col2, col3 …] / No}

| Column Header | Field | DataType | Format | Alignment |
|---|---|---|---|---|
| {Column 1 Header} | {FieldName1} | {String \| Integer \| Decimal \| DateTime} | {see formats below} | {Left \| Center \| Right} |
| {Column 2 Header} | {FieldName2} | Decimal | $0,000.00 / ($0,000.00) | Right |
| {Column 3 Header} | {FieldName3} | DateTime | MM/DD/YYYY | Center |
| {Column 4 Header} | {FieldName4} | Integer | 0,000 / (0,000) | Right |
| {Column 5 Header} | {FieldName5} | String | as-stored | Center |

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

### Tab 2: {Tab Name}  *(remove if report has only one tab)*

- **Grouping:** {e.g. TerminalNo → GameName (ascending)}
- **Totals row:** {Yes — sum [col1, col2] / No}

| Column Header | Field | DataType | Format | Alignment |
|---|---|---|---|---|
| {Column 1 Header} | {FieldName1} | String | as-stored | Center |
| {Column 2 Header} | {FieldName2} | Decimal | $0,000.00 / ($0,000.00) | Right |

---

## Business Rules / Requirements

<!--
  List every "The report shall…" statement from the FRD Requirements section.
  Each bullet = one atomic business rule.
  For calculated fields, write the formula using (+) (−) notation as in the FRD.
-->

- The report shall include {describe the data scope — date range, filters applied}.
- The report shall define **{CalculatedField1}** as {Expression using (+) (−) notation}.
- The report shall define **{CalculatedField2}** as {Expression}.
- The report shall {group / sort / filter} data by {criteria}.
- The report shall cite the totals of each {metric / numeric} column.
- {Add additional requirements as needed.}

---

## Header / Footer

<!--
  These are fixed for ALL paginated reports per Section 2.1.
  Only the parameter list changes per report — update it below.
-->

- **Report Header (left):** Missouri Lottery logo
- **Report Header (centre):** Report title — `{Report Title}`
- **Report Header (right):** Parameters: {list parameter labels} | Run: MM/DD/YYYY HH:MM:SS
- **Report Footer (left):** `{Report Title}`
- **Report Footer (right):** Page `[&PageNumber]` of `[&TotalPages]`

---

## General Formatting  *(Section 2.1 — applies to all reports)*

- Any access restrictions to reports will be managed through assigned Security roles.
- The field length of all column and row values extracted from the database will be
  accommodated to their full lengths; formats will be retained unless specified otherwise.
- The header shall cite the defined parameters and the run date and time of the report output.
- The report footer shall cite the report title and output page.

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
