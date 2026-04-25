# BO-to-PBI Converter

Automates the migration of SAP BusinessObjects WebI reports to Power BI by extracting report metadata via the BO REST API and generating Power BI paginated report (.rdl) files.

---

## What It Does

The tool connects to a SAP BusinessObjects server, enumerates all WebI reports, and extracts:

- **Report parameters** (name, data type, required/optional, single/multiple select)
- **Data providers** (universe name, data source type)
- **Layout columns** (column headers per data provider tab)
- **SQL queries** (the actual SQL behind each data provider, including custom/freehand SQL)
- **Folder paths** (full BO folder hierarchy, e.g. `Public Folder/Connecticut/Reports/CAP`)

It then generates Power BI report artifacts in three phases:

| Phase | What It Produces | Output Location |
|-------|-----------------|-----------------|
| **Phase 1 — Extract** | JSON metadata file + SQL files per report | `output/bo-extracted/` + `output/bo-sql/` |
| **Phase 2 — Specs** | Markdown spec documents for human review | `output/bo-specs/` |
| **Phase 3 — RDL** | Power BI paginated report (.rdl) files | `output/bo-rdl/` |

---

## Pipeline

```
SAP BusinessObjects REST API
        |
        |  Phase 1: Extract metadata + SQL
        v
   bo_extracted.json  +  *.sql files
        |
        |  Phase 2: Generate review specs
        v
   *.md spec files (one per report)
        |
        |  Phase 3: Generate RDL reports
        v
   *.rdl paginated report files
```

Each phase can be run independently, allowing human review at any checkpoint.

---

## Key Features

- **Automated enumeration** — discovers all WebI reports on the server with paginated API calls
- **SQL extraction** — pulls the actual SQL query behind each report's data provider, preserving multi-query and custom SQL scenarios
- **Folder-aware filtering** — extracts only reports under specified BO folder paths (e.g. `Public Folder/Connecticut/Reports`); supports multiple folder targets
- **Report name filtering** — filter extraction to specific reports by name
- **Human review checkpoint** — generates readable markdown specs between extraction and RDL generation, allowing developers to verify and adjust before producing final reports
- **Datasource detection** — automatically classifies reports as Semantic Model, Snowflake ODBC, or DB2 ODBC based on configurable keyword matching
- **Full test coverage** — 25 automated tests covering client auth, enumeration, extraction, filtering, error handling, and end-to-end integration

---

## Usage

### Prerequisites

- Python 3.9+
- Network access to the BO server
- BO credentials (username in config, password via environment variable)

### Running

```bash
# Set the BO password
export BO_PASSWORD=your_password

# Run the full pipeline (extract + specs + rdl)
python convert_bo_reports.py

# Or run individual phases
python convert_bo_reports.py --only extract    # Phase 1: BO API -> JSON + SQL
python convert_bo_reports.py --only specs      # Phase 2: JSON -> .md specs
python convert_bo_reports.py --only rdl        # Phase 3: .md specs -> .rdl files

# Filter by folder (comma-separated for multiple)
python convert_bo_reports.py --folder "Connecticut/Reports/CAP, Connecticut/Reports/Finance"

# Filter by report name
python convert_bo_reports.py --report "Daily Sales"
```

---

## Configuration

All settings live in `pbi.properties` under the `[bo]` section:

```ini
[bo]
host = http://10.17.56.65:8080/biprws
username = administrator
# Password via BO_PASSWORD env var — never stored in config
# Folder paths to extract (comma-separated for multiple folders)
root_folder = Public Folder/Connecticut/Reports
# HTTP timeout in seconds for BO API calls (default: 30)
timeout = 30
```

The `--folder` CLI flag overrides the config value for one-off extractions.

### Universe-to-datasource mapping

An optional `[bo_universe_map]` section maps BO universe names to PBI targets. Values can be either a **datasource type** or a **semantic model name**:

```ini
[bo_universe_map]
# Map to a specific semantic model (implies datasource_type = semantic_model)
LocationSales = MO_Sales
InstantPackInventory = MO_Inventory

# Map to a datasource type (model inferred via [model_keywords])
Transactional = snowflake
Claims = db2
```

Keys are case-insensitive. If the value matches a known datasource type (`snowflake`, `db2`, `semantic_model`), it's treated as a type. Otherwise it's treated as a semantic model name, which automatically sets the datasource type to `semantic_model`.

When no `[bo_universe_map]` entry matches, the tool falls back through a priority chain:

1. **`[bo_universe_map]`** — explicit universe name → datasource type or semantic model (deterministic)
2. **BO `dataSourceType`** — structural mapping from the BO API (`unx`/`unv` → `snowflake`)
3. **`[datasource_keywords]`** — name/summary/notes keyword heuristic
4. **`default_datasource`** — final fallback

For jurisdictions where all universes point to the same backend (e.g. all Snowflake), the `dataSourceType` mapping (level 2) handles everything automatically — no `[bo_universe_map]` needed. The map is most useful when you need to route specific universes to specific semantic models, or when multiple `unx` universes point at different backends.

---

## Output Examples

### Extracted SQL (`output/bo-sql/Daily_Sales_Report.sql`)

```sql
-- Report: Daily Sales Report
-- Extracted from SAP BusinessObjects

-- Data Provider: Sales
-- Universe: LocationSales
-- Data Source Type: unx

SELECT DIMCORE.LOCATIONS.LOCATION_NUMBER,
       DIMCORE.LOCATIONS.LOCATION_NAME,
       DIMCORE.LOCATIONS.PRIMARY_CITY,
       sum(FINANCIAL.FINANCIAL_DAILY.NET_SALES_AMOUNT)
FROM DIMCORE.LOCATIONS, FINANCIAL.FINANCIAL_DAILY
WHERE FINANCIAL.FINANCIAL_DAILY.LOCATION_KEY = DIMCORE.LOCATIONS.LOCATION_KEY
GROUP BY DIMCORE.LOCATIONS.LOCATION_NUMBER,
         DIMCORE.LOCATIONS.LOCATION_NAME,
         DIMCORE.LOCATIONS.PRIMARY_CITY
```

### Generated Spec (`output/bo-specs/daily-sales-report.md`)

A structured markdown document containing:
- Report metadata (name, format, folder, legacy path)
- Data source configuration
- Parameter definitions (labels, types, required/optional)
- Layout columns per data provider tab
- Business rules and requirements

### Generated RDL (`output/bo-rdl/daily-sales-report.rdl`)

A complete Power BI paginated report XML file with:
- Data source and dataset definitions
- Report parameters matching the original BO prompts
- Tablix layout with column headers from the BO report
- Header/footer with standard branding

---

## Architecture

| Module | Responsibility |
|--------|---------------|
| `bo_converter/config.py` | Reads BO connection settings from `pbi.properties` |
| `bo_converter/bo_client.py` | BO REST API client — authentication, document enumeration, per-report metadata extraction |
| `bo_converter/bo_extractor.py` | Phase 1 orchestrator — filtering, batch extraction, JSON + SQL file output |
| `bo_converter/bo_spec_generator.py` | Phase 2 — normalises extracted data and generates markdown specs |
| `convert_bo_reports.py` | CLI entry point — routes phases and applies filters |

Phase 3 (RDL generation) reuses the existing `report_generator` module's Path B pipeline — no duplication of RDL generation logic.

---

## Current Extraction Stats

From the Connecticut BO server (`ctsq1riarpiap01`):

- **241 total WebI documents** on the server
- **161 reports** under `Public Folder/Connecticut/Reports` (across 17 subfolders)
- **80 reports** under `User Folders/Administrator` (personal folders for Julia, Colin, Kayla, and templates)
- **155 reports extracted** with SQL in the most recent run (~5 minutes extraction time)
- **155 SQL files** generated

---

## Known Limitations

1. **Folder filtering enumerates all documents first.** Phase 1 fetches the full document list from the BO server and resolves folder paths client-side before applying folder filters. With 241+ documents this adds overhead proportional to total document count, not filtered count. The BO `/infostore` endpoint supports querying children by parent folder ID, which could eliminate the enumerate-then-filter approach, but would require a larger API rework. Current extraction time (~5 minutes for 241 docs) is acceptable.

2. **Layout is derived from data provider columns, not the report layout.** The BO REST API exposes data provider dictionaries (columns, data types) but the actual report-level layout (tab grouping, crosstab vs. table, column display order, calculated report-level columns) would require parsing the `/reports` endpoint. The generated specs list correct column headers but may not reflect the visual organization of the original BO report. Developers should verify layout during the spec review step (Phase 2).

3. **No end-to-end test for Phase 3 (RDL generation).** The integration test covers Phase 1 -> Phase 2 (extract -> specs). Phase 3 is covered implicitly through `report_generator.spec_to_rdl` tests, but there is no bo_converter-specific test that verifies the full three-phase pipeline produces valid `.rdl` output.

---

## Integration with Existing Tools

The bo-converter is part of the `pbi-automation` repo and integrates with the existing report generation pipeline:

```
pbi-automation/
├── report_generator/    — FRD Word doc -> Power BI reports (existing)
├── model_generator/     — Snowflake -> Semantic Models (existing)
└── bo_converter/        — SAP BO WebI -> Power BI reports (new)
```

All three tools share common infrastructure (config, templates, output directories) but operate independently.
