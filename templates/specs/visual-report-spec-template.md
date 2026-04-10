# Visual Report Spec: {Report Title}

<!--
  VISUAL REPORT TEMPLATE (.pbip)
  ─────────────────────────────────────────────────────────────────────────────
  Use this template to document a Performance Wizard VISUAL report.
  Visual reports present one or more interactive data visualisations across
  one or more pages.  They support:
    • Real-time filter interaction (no re-run required)
    • Charts, graphs, tables, cards, matrices, slicers
    • Global filters (all pages), page filters, and local (visual-level) filters
  Output format: Power BI Project (.pbip) — PBIR + TMDL format

  HOW TO USE
  1. Replace every {Placeholder} with the actual value from the FRD.
  2. Fill in the Filters, Semantic Model, and Pages sections.
  3. Add business rules / DAX measures in the Requirements section.
  4. Copilot will use this file to build the .pbip report folder structure.

  PBIP FOLDER STRUCTURE GENERATED
  ──────────────────────────────────
  {ReportName}.Report/
    definition/
      report.json                ← report-level settings (theme, filters)
      pages/
        pages.json               ← ordered page list
        {Page1Name}/
          page.json              ← display name, canvas size
          visuals/
            {visualId}/
              visual.json        ← visual type, position, field bindings
        {Page2Name}/  …
  {ReportName}.SemanticModel/    ← (if new model; omit if binding to existing)
    definition/
      model.tmdl
      tables/
        {TableName}.tmdl         ← columns + measures
      relationships.tmdl
      expressions.tmdl           ← M queries / parameters

  SECTION 2.1 REQUIREMENTS (apply to ALL visual reports automatically)
    • Header : Latest date of data availability
    • Logo   : Missouri Lottery logo, top-left corner
    • No traditional page footer (visual reports are screen-first)
    • Data   : see "General Formatting" section at the bottom
-->

---

## Metadata

- **Report Title:** {Report Title}
- **Legacy Path:** `{01. Public Folders\Missouri\...\Legacy Report Name}`
- **Legacy Users:** {Brightstar | Lottery Sales | Lottery Marketing | …}
- **Description:** {One-sentence description of what the report shows and its primary audience.}
- **Report Format:** Visual (.pbip)
- **Output Folder:** {Reports - Brightstar | Reports - Lottery Sales | …}
- **Notes:** {Scheduling notes, special delivery, or leave blank.}

---

## Data Source

- **Semantic model:** {Existing shared model name — or "New model defined below"}
- **Snowflake schema(s):** {e.g. financial, dimcore, instant}
- **Connection mode:** {DirectQuery | Import}

---

## Semantic Model

<!--
  Complete this section only if the report uses a NEW semantic model.
  If it binds to an existing shared .SemanticModel, write the model name and skip
  the Tables / Measures / Relationships sub-sections.

  For an EXISTING model: just write the binding name, e.g.
    **Binds to:** `MO_Sales_Shared.SemanticModel`
-->

### Tables

<!--
  List every Snowflake table / view that needs to be loaded.
  The "Load Mode" column controls DirectQuery vs Import per table.
-->

| Table Name (TMDL) | Snowflake Source | Load Mode | Key Columns |
|---|---|---|---|
| {TableName1} | {schema.TABLE_NAME} | {DirectQuery \| Import} | {PK / FK columns} |
| {TableName2} | {schema.TABLE_NAME} | {DirectQuery \| Import} | {PK / FK columns} |

### Measures

<!--
  List every DAX measure needed by this report.
  Use the exact measure name that will appear in field pickers.
-->

| Measure Name | Table | DAX Expression | Format | Notes |
|---|---|---|---|---|
| {Measure 1} | {TableName} | `{DAX formula}` | {$0,000.00 \| 0,000 \| 0.0%} | {Brief note} |
| {Measure 2} | {TableName} | `{DAX formula}` | {format} | {note} |

<!--
  COMMON DAX PATTERNS:
    Net Sales        = SUM(table[GrossSales]) - SUM(table[Cancels]) - SUM(table[FreeTickets])
    YoY Change %     = DIVIDE([CurrentYear Sales] - [PriorYear Sales], [PriorYear Sales])
    Avg Weekly Sales = AVERAGEX(VALUES(dim_dates[WeekKey]), [Net Sales])
    Running Total    = CALCULATE([Net Sales], DATESYTD(dim_dates[Date]))
-->

### Relationships

| From Table | From Column | To Table | To Column | Cardinality | Direction |
|---|---|---|---|---|---|
| {FactTable} | {FK_column} | {DimTable} | {PK_column} | Many-to-One | Single |

---

## Filters

<!--
  FILTER TYPES (Section 2.1):
  ┌────────────┬──────────────────────────────────────────────────────────────┐
  │ Global     │ Applies to all visualisations on ALL pages of the report.   │
  │ Page       │ Applies to all visualisations on ONE specific page only.    │
  │ Local      │ Applies to ONE specific visualisation only.                 │
  └────────────┴──────────────────────────────────────────────────────────────┘

  A label ending in * requires a specific value (cannot leave as "All").
  Filter Context: "Global (all pages)" | "Page: {Page Name}" | "Visual: {Visual Title}"
-->

| Filter Label | Filter Type | Filter Context | Single / Multiple | Default / Notes |
|---|---|---|---|---|
| {Filter 1}* | Global | Global (all pages) | Multiple | Default: {Most recent month / All / …} |
| {Filter 2} | Global | Global (all pages) | Multiple | Default: All |
| {Filter 3} | Page | Page: {Page Name} | Single | Default: {value} |
| {Filter 4} | Local | Visual: {Visual Title} | Multiple | Default: All |

---

## Pages

<!--
  ADD ONE "### Page N: {Name}" SECTION PER REPORT PAGE.
  Canvas size is typically 1280 × 720 (16:9) unless specified.

  VISUAL TYPES supported in Power BI (.pbip):
  ┌─────────────────┬────────────────────────────────────────────────────────┐
  │ tableEx         │ Standard table (rows × columns, optional totals)       │
  │ matrix          │ Cross-tab / pivot table (row groups, column groups)    │
  │ barChart        │ Clustered or stacked bar / column chart                │
  │ lineChart       │ Line or area chart (time series)                       │
  │ card            │ Single-number KPI tile                                 │
  │ multiRowCard    │ Multiple KPI values in card layout                     │
  │ slicer          │ Interactive filter widget (dropdown / list / range)    │
  │ pieChart        │ Pie or donut chart                                     │
  │ scatterChart    │ Scatter / bubble chart                                 │
  │ map / filledMap │ Geographic map visual                                  │
  │ gauge           │ Radial gauge (target vs actual)                        │
  └─────────────────┴────────────────────────────────────────────────────────┘
-->

### Page 1: {Page Name}

- **Canvas size:** 1280 × 720
- **Page filter(s):** {Filter label(s) that apply only to this page — or "None"}

#### Visual 1: {Visual Title}

- **Type:** `{tableEx | barChart | lineChart | card | matrix | slicer | …}`
- **Position:** top-left  *(adjust as needed: top-right | bottom-left | full-width | …)*
- **Rows / Axis:** `{Table.ColumnName}` — {description, e.g. "one row per retailer"}
- **Columns / Legend:** `{Table.ColumnName}` *(for matrix / grouped charts — omit if N/A)*
- **Values / Measures:**
  - `[{Measure 1}]` — {brief description}
  - `[{Measure 2}]` — {brief description}
- **Totals:** {Yes — Grand Total row at bottom | No}
- **Sort:** {default sort field and direction}
- **Conditional formatting:** {e.g. "red if Net Sales < 0" — or "None"}
- **Notes:** {any special behaviour, drill-through, tooltip, etc.}

#### Visual 2: {Visual Title}

- **Type:** `{barChart | lineChart | card | …}`
- **Position:** top-right
- **Axis (X):** `{Table.ColumnName}` — {e.g. "Month"}
- **Values (Y):**
  - `[{Measure 1}]`
- **Legend:** `{Table.ColumnName}` *(omit if N/A)*
- **Notes:** {e.g. "secondary Y-axis for …"}

#### Visual 3: {Visual Title}  *(add / remove visuals as needed)*

- **Type:** `card`
- **Values:**
  - `[{KPI Measure}]`
- **Title displayed:** "{Label shown above the card}"

---

### Page 2: {Page Name}  *(add / remove pages as needed)*

- **Canvas size:** 1280 × 720
- **Page filter(s):** {None}

#### Visual 1: {Visual Title}

- **Type:** `tableEx`
- **Rows:** `{Table.ColumnName}`
- **Values / Measures:**
  - `[{Measure 1}]`
  - `[{Measure 2}]`
- **Totals:** Yes
- **Sort:** `[{Measure 1}]` DESC

---

## Business Rules / Requirements

<!--
  List every "The report shall…" statement from the FRD Requirements section.
  Include DAX definitions for any calculated measures that have a formula
  specified in the FRD.
-->

- The report shall include data for {describe scope — game type, date range, etc.}.
- The report shall, on Page 1 ({Page Name}), {describe grouping / sorting / filtering}.
- The report shall, on Page 1, cite totals for each {metric} column.
- The report shall define **{MeasureName}** as {formula in (+) (−) notation from FRD}.
- The report shall, on Page 2 ({Page Name}), {describe behaviour}.
- {Add additional requirements as needed.}

---

## Header / Footer

<!--
  Visual reports display the latest data availability date in the header.
  There is no traditional page footer.
-->

- **Report Header:** Latest date of data availability (top of report canvas)
- **Logo:** Missouri Lottery logo, top-left corner

---

## General Formatting  *(Section 2.1 — applies to all reports)*

- Any access restrictions to reports will be managed through assigned Security roles.
- The field length of all column and row values extracted from the database will be
  accommodated to their full lengths; formats will be retained unless specified otherwise.
- The report header shall cite the latest date of data availability.
- The justification of all values shall align with the formatting of the Visual Analytics product.

**Data formats:**

- Date: `MM/DD/YYYY`
- Time: `HH:MM:SS` (24-hour)
- Currency: `$0,000.00` · negatives: `($0,000.00)` · zeros: `$0.00`
- Counts: `0,000` · negatives: `(0,000)` · zeros: `0`
- Phone: `123-456-7890`
- Codes / numbers: formatted as stored unless otherwise specified
- Justification of values: follows Power BI Visual Analytics product defaults
  (numeric → right; text → left; dates → center)
