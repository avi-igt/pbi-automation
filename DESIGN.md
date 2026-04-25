# pbi-automation — Design Document

## Overview

`pbi-automation` is the Power BI automation platform for the Brightstar Lottery Performance Wizard product. It contains three independent tools that share a repo, a combined `requirements.txt`, and common output/template directories:

| Tool | Package | Entry point | Datasource |
|---|---|---|---|
| report-generator | `report_generator/` | `generate_reports.py` | FRD `.docx` Word file |
| model-generator | `model_generator/` | `generate_models.py` | Snowflake via `semantic.properties` |
| bo-converter | `bo_converter/` | `convert_bo_reports.py` | SAP BusinessObjects REST API via `pbi.properties` |

Each tool has its own config file and can be run independently. bo-converter delegates to `report_generator` modules for spec generation and RDL output (Path B).

---

## report_generator Architecture

### Purpose

Parses a Functional Requirements Document (FRD `.docx`, Performance Wizard / ADO format) into structured JSON, then generates three types of Power BI output: `.rdl` paginated report XML, `.pbip` visual report folder structures, and `.md` human-readable spec documents.

### Layers

```
FRD.docx
  └── frd_parser.py        ← parsing layer: .docx → structured JSON dict
        └── frd_parsed.json   (human checkpoint — review and edit here)
              ├── rdl_generator.py    ← generation: JSON → .rdl XML
              ├── pbip_generator.py   ← generation: JSON → .pbip folder structure
              └── spec_generator.py   ← generation: JSON → .md spec doc

spec_parser.py             ← Path B parser: .md spec → report dict
  ├── spec_to_rdl.py       ← Path B generation: spec → .rdl
  └── spec_to_pbip.py      ← Path B generation: spec → .pbip
```

### frd_parser.py — Parsing Layer

The FRD uses **Azure DevOps SDT content controls** embedded in Word — the parser uses `lxml` to extract `w:sdt` elements rather than plain paragraph text. Each control contains structured sub-sections (Summary, Parameters, Filters, Layout, Requirements).

Key decisions:
- Output is a plain Python dict serialised to JSON — the checkpoint format is stable and human-editable
- `datasource_type` is inferred at parse time via `config.py` keyword matching; it can be overridden by editing the JSON
- `report_format` (Paginated vs Visual) is parsed from the FRD's "Report Format" field

### Generation Layer

All three generators (`rdl_generator.py`, `pbip_generator.py`, `spec_generator.py`) are pure functions: they receive the parsed report dict and return file content (or write to disk). They read config from `config.py` singletons but do not modify any shared state.

**RDL generation** builds the full XML from scratch (no base template file). Every element — schema declarations, data source, dataset, parameters, tablix, header, footer — is generated from the report dict. The XML namespace is `http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition`.

**PBIP generation** produces a folder per report: `definition.pbir` (semantic model binding via `byPath`), `report.json`, `pages/`, `visuals/`, and a developer `README.md` with a requirements checklist.

**Spec generation** writes structured `.md` files consumable by Path B. The format is designed to be both human-readable (documentation artifact) and machine-parseable (input for `spec_parser.py`).

### Path B — Spec → Reports

Path B allows a developer to confirm/edit a spec `.md` (filling in the real semantic model name, SQL query, or connection string) and regenerate reports from the confirmed spec rather than the original FRD. `spec_parser.py` reads the `.md` format and injects confirmed values as `_spec_*` override keys that take precedence over auto-inferred values.

Path B output lands in `output/from-spec/` to avoid overwriting Path A output.

### Configuration — config.py

`config.py` reads `pbi.properties` (INI format) and exposes:
- `detect_datasource(name, summary)` → `"snowflake"` | `"db2"` | `"semantic_model"`
- `select_model(name, summary)` → model name string
- DSN names, workspace, host settings

Detection is keyword-based and order-sensitive. The `[datasource_keywords]` section is checked before `[model_keywords]`. The last entry in `[model_keywords]` is the catch-all fallback.

### Path Resolution

```python
# report_generator/config.py
_REPO_ROOT = Path(__file__).parent.parent  # → pbi-automation/
```

`pbi.properties` → `pbi-automation/pbi.properties`
`templates/` → `pbi-automation/report_generator/templates/`
`sql/` → `pbi-automation/report_generator/sql/`

---

## model_generator Architecture

### Purpose

Generates production-ready Power BI semantic model artifacts by:
1. Reading a `semantic.properties` config file (models, dimensions, Snowflake connection)
2. Introspecting Snowflake table schemas via `SHOW COLUMNS`
3. Building TMDL content (tables, measures, relationships, expressions)
4. Building a PBIR placeholder `.Report` folder (byPath binding + theme)
5. Writing both output folders to disk

### Layers

```
semantic.properties
  └── config.py               ← reads config; ModelDef + DimensionDef dataclasses
        └── model_generator.py    ← orchestrator: one model → SemanticModel + Report
              ├── snowflake_client.py  ← introspect: SHOW COLUMNS → column metadata
              ├── tmdl_builder.py     ← pure builders: column metadata → TMDL strings
              └── report_builder.py   ← pure builders: ModelDef → PBIR JSON strings
```

### config.py — Configuration Layer

Reads `semantic.properties` and constructs:
- `SnowflakeConfig` dataclass — connection params, per-env overrides (`[snowflake.<env>]`)
- `DimensionDef` dataclass — alias, schema, table, primary key, strategy (A/B), optional inherit
- `ModelDef` dataclass — display name, fact schema/table, dimension list, join key overrides
- `MeasureSuffixDef` dataclass — suffix, data type, format string (from `[measure_suffixes]`)

Environment overrides (`--env d1v1`) merge `[snowflake.d1v1]` fields on top of `[snowflake]`. The `.privatelink` suffix in `account` is a requirement for non-production environments.

### snowflake_client.py — Introspection Layer

Uses `snowflake-connector-python` to execute `SHOW COLUMNS IN TABLE <schema>.<table>` and parse the result into a list of `ColumnInfo` namedtuples (name, data_type, nullable). No schema inference or guessing — the actual Snowflake schema is authoritative.

The client is used as a context manager (`with SnowflakeClient(cfg.snowflake) as sf:`), which opens the connection once and keeps it open for all models in a run.

### tmdl_builder.py — TMDL Build Layer

Pure string-building functions (no file I/O). Each function returns a TMDL string for one artifact:
- `build_table_tmdl(table_name, columns)` — full table definition with columns and measures
- `build_relationships_tmdl(model_def, fact_column_names, dim_defs)` — no-op stub (returns `""`); dimensions are joined via merged queries, not TMDL relationships
- `build_expressions_tmdl(snowflake_cfg)` — Snowflake connection parameters

**Star schema column rules** (applied in `build_table_tmdl`):

| Column | Output |
|---|---|
| Exact match on dimension join key | Hidden, `int64` — relationship column only |
| Ends in a configured `[measure_suffixes]` suffix | Hidden source column + `CALCULATE(SUM(...))` measure |
| Other `ALL_UPPERCASE` | Hidden |
| `Title Case` | Visible |

Suffix matching uses `[measure_suffixes]` from `semantic.properties` — no code changes needed to add new types.

### report_builder.py — PBIR Build Layer

Pure string-building functions (no file I/O) that produce all files required for a `.Report` folder:
- `build_definition_pbir(model_def)` — `byPath` reference to sibling `.SemanticModel`
- `build_report_json()` — theme + canvas settings
- `build_page_json(page_id, model_def)` — single placeholder page
- `build_placeholder_visual(visual_id, model_def)` — textbox with report name
- Supporting files: `.platform`, `localSettings.json`, `pages.json`, `version.json`

`new_report_ids()` generates fresh UUID pairs for page and visual IDs on every run (lineageTag UUIDs are similarly regenerated — expected, no semantic meaning).

### model_generator.py — Orchestration Layer

`ModelGenerator.generate(model_def, output_dir)` orchestrates one model:

1. Introspect fact table columns via `snowflake_client`
2. Introspect each dimension's table columns
3. Call `tmdl_builder` functions to build TMDL strings
4. Write `.SemanticModel` folder structure to disk
5. Call `report_builder` functions to build PBIR strings
6. Write `.Report` folder structure to disk (including `shutil.copy2` of the theme file)

`_generate_semantic_model()` and `_generate_report()` are separate private methods with clear file-write responsibilities. All file I/O is isolated to `model_generator.py` — builders are pure.

### Path Resolution

```python
# model_generator/config.py
_REPO_ROOT = Path(__file__).parent.parent  # → pbi-automation/
```

`semantic.properties` → `pbi-automation/semantic.properties`
`dimensions/` → `pbi-automation/model_generator/dimensions/`
`templates/BaseThemes/` → `pbi-automation/model_generator/templates/BaseThemes/`

---

## bo_converter Architecture

### Purpose

Extracts metadata from SAP BusinessObjects WebI reports via the BO REST API (biprws/raylight) and produces Power BI report artifacts. The tool handles the full lifecycle: enumerate documents, extract parameters/layout/SQL, generate `.md` specs, and produce `.rdl` paginated reports.

### Layers

```
BO REST API (biprws)
  └── bo_client.py         ← API client: auth, enumerate, extract per-report metadata
        └── bo_extractor.py    ← Phase 1 orchestrator: filter, extract all, write JSON + SQL
              └── bo_spec_generator.py  ← Phase 2: normalise + delegate to report_generator.spec_generator
                    └── spec_to_rdl.py      ← Phase 3: existing Path B (report_generator module)
```

### bo_client.py — API Client Layer

Wraps the SAP BO REST API. Used as a context manager (`with BoClient(config) as client:`), which handles logon/logoff lifecycle and maintains an HTTP session.

Key methods:
- `enumerate_webi_documents()` — paginated GET of `/raylight/v1/documents` (page size 50)
- `extract_report(doc)` — extracts parameters, data providers, layout columns, SQL, and folder path for one document
- `resolve_folder_path(doc)` — resolves `folderId` to a full path by walking the `up.__deferred.uri` chain, maps BO "Root Folder" to "Public Folder"

Folder paths are cached in `_folder_path_cache` to avoid redundant API calls across documents in the same folder tree.

SQL extraction uses the `/raylight/v1/documents/{id}/dataproviders/{dpId}/queryplan` endpoint. Custom/freehand SQL is detected via the `@custom` attribute.

### bo_extractor.py — Phase 1 Orchestrator

`extract_all()` coordinates enumeration, filtering, extraction, and output:

1. Enumerate all WebI documents via `bo_client`
2. Apply folder filter (comma-separated, from `root_folder` config or `--folder` CLI)
3. Apply report name filter (from `--report` CLI)
4. Extract each document via `bo_client.extract_report()`
5. Write `bo_extracted.json` to `output/bo-extracted/`
6. Write per-report `.sql` files to `output/bo-sql/`

Folder filtering supports multiple paths (comma-separated). Each path is matched as a case-insensitive substring against the resolved folder path.

### bo_spec_generator.py — Phase 2

Normalises BO JSON into the shape that `report_generator.spec_generator.generate_md()` expects, then delegates rendering. This avoids duplicating any markdown formatting logic. Also uses `report_generator.config` for datasource and semantic model inference via keyword matching.

### Phase 3 — RDL Generation

Phase 3 is delegated entirely to the existing `report_generator.spec_to_rdl.generate_rdl_from_specs_dir()`. No bo-converter-specific code is involved — the `.md` specs produced by Phase 2 are compatible with the Path B parser (`spec_parser.py`).

### config.py — Configuration

Reads the `[bo]` section from `pbi.properties`:
- `host` — BO REST API base URL
- `username` — BO logon username (password via `BO_PASSWORD` env var)
- `root_folders` — list of folder paths to filter (comma-separated in config)
- `request_delay` — seconds between API calls (rate limiting)

### Path Resolution

```python
# bo_converter/config.py
_REPO_ROOT = Path(__file__).parent.parent  # → pbi-automation/
```

`pbi.properties` → `pbi-automation/pbi.properties`

---

## Shared Conventions

### Config file format

Both tools use INI-format `.properties` files (Python `configparser`). Sections are used to group related settings. Neither tool accepts command-line overrides of individual config values — all deployment-specific settings belong in the config file.

### Output directory layout

```
output/
  json/           ← report_generator: frd_parsed.json
  specs/          ← report_generator: .md review docs
  rdl/            ← report_generator: .rdl files
  pbip/           ← report_generator: .pbip folders
  from-spec/      ← report_generator: Path B outputs
  models/         ← model_generator: .SemanticModel + .Report pairs
  bo-extracted/   ← bo_converter: bo_extracted.json (Phase 1)
  bo-sql/         ← bo_converter: extracted SQL files (Phase 1)
  bo-specs/       ← bo_converter: .md spec files (Phase 2)
  bo-rdl/         ← bo_converter: .rdl files (Phase 3)
```

The three tools write to separate output subdirectories and do not interfere with each other.

### No shared runtime state

The three tools have no shared in-memory state. They can all be imported in the same Python process without conflict. bo-converter imports `report_generator` modules for spec generation and RDL output but does not modify any shared state.

### Templates

`model_generator/templates/BaseThemes/CY24SU10.json` is the only template consumed at runtime (by `model_generator.py`). All other templates under `report_generator/templates/specs/` are reference documents for human review, not parsed by any tool.

---

## Extension Points

### report_generator

| What | Where |
|---|---|
| New semantic model | Add to `[datasets]` and `[model_keywords]` in `pbi.properties` |
| New datasource type keyword | Add to `[datasource_keywords]` in `pbi.properties` |
| New ODBC data source variant | Add a branch in `rdl_generator.py` `generate_rdl()` + DSN in `[odbc]` |
| New FRD field | Add to the `fields` list in `frd_parser.py` `parse_summary()` |
| New visual type | Add keywords to `_CHART_HINTS` and a `make_*_visual()` function in `pbip_generator.py` |
| New state / environment | Copy `pbi.properties`, update workspace, GUIDs, DSNs, keywords — no code changes |

### model_generator

| What | Where |
|---|---|
| New measure suffix type | Add to `[measure_suffixes]` in `semantic.properties` — no code changes |
| New model | Add `[model.*]` section to `semantic.properties` — no code changes |
| New dimension | Add entry to `[dimensions]` + Strategy A YAML (or Strategy B inline) — no code changes |
| New environment | Add `[snowflake.<env>]` section to `semantic.properties` — no code changes |
| New TMDL content | Add builder function to `tmdl_builder.py` and call from `model_generator.py` |

### bo_converter

| What | Where |
|---|---|
| New BO server | Update `[bo]` section in `pbi.properties` (host, username) — no code changes |
| Different folder tree | Update `root_folder` in `pbi.properties` or use `--folder` CLI — no code changes |
| Multiple folder trees | Comma-separate paths in `root_folder` or `--folder` — no code changes |
| New output phase | Add phase in `convert_bo_reports.py` `main()` and wire into `--only` choices |
| PBIP output from BO | Use existing `spec_to_pbip.py` against `output/bo-specs/` (already compatible) |

---

## What These Tools Do Not Do

- **Do not publish** to Power BI Service or Fabric — all output is for local review and manual deployment
- **Do not modify** existing reports — all output is net-new files in `output/`
- **Do not validate** DAX expressions or semantic model correctness — use `pbi-cli` for live validation
- **Do not manage** Liquibase changesets or Snowflake DDL — that is the responsibility of `lpc-v1-app-ldi-dh`
- **Do not store** credentials — `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` are environment variables only
