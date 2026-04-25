# BO-to-PBI Converter — Design Spec

## Purpose

A new `bo_converter/` module in `pbi-automation` that extracts metadata from SAP BusinessObjects WebI reports via the BO REST API and generates Power BI `.md` spec files for human review, feeding into the existing Path B workflow (`spec_to_rdl.py`).

This enables bulk conversion of hundreds of BO WebI reports to Power BI paginated reports (RDL) through a scaffolding approach — automated extraction, human review, then generation.

## Architecture

### Pipeline

```
BO REST API (http://10.17.56.65:8080/biprws)
        |  Phase 1
  bo_extractor.py  -->  output/bo-extracted/bo_extracted.json
        |  Phase 2
  bo_spec_generator.py  -->  output/bo-specs/*.md
        |  (existing Path B)
  spec_to_rdl.py  -->  output/from-spec/rdl/*.rdl
```

Phase 2 normalises the BO JSON into the same schema that `spec_generator.py` already understands, then delegates to it. Report formatting logic is not duplicated.

### Module Structure

```
pbi-automation/
├── convert_bo_reports.py        # entry point (repo root)
└── bo_converter/
    ├── __init__.py
    ├── config.py                # reads [bo] section from pbi.properties
    ├── bo_client.py             # REST API: auth, enumerate, per-report extraction
    ├── bo_extractor.py          # orchestrates extraction --> bo_extracted.json
    └── bo_spec_generator.py     # normalises BO JSON --> spec_generator input schema
```

### Relationship to Existing Tools

- `bo_converter/config.py` wraps `report_generator/config.py` (imports and extends it) so the same `pbi.properties` file serves both tools and `infer_datasource()` / `infer_semantic_model()` keyword logic is shared without duplication.
- `bo_spec_generator.py` delegates to `spec_generator.py` for the actual `.md` rendering after normalising field names/shapes.
- Output specs are compatible with `spec_to_rdl.py` (Path B) with no modifications.

## BO REST API Calls

`bo_client.py` makes these calls per session:

| Step | Endpoint | Purpose |
|---|---|---|
| Auth | `POST /logon/long` | Session token (`X-SAP-LogonToken` header) |
| Enumerate | `GET /infostore?query=SELECT SI_ID,SI_NAME,SI_DESCRIPTION,SI_PARENT_FOLDER,SI_PATH FROM CI_INFOOBJECTS WHERE SI_KIND='Webi'` | All WebI docs with folder path |
| Metadata | `GET /raylight/v1/documents/{id}` | Name, description |
| Parameters | `GET /raylight/v1/documents/{id}/parameters` | Prompts |
| Data providers | `GET /raylight/v1/documents/{id}/dataproviders` | Universe/connection name |
| Report elements | `GET /raylight/v1/documents/{id}/reports/{rid}/elements` | Table column headers |
| Logoff | `DELETE /logon/long` | Clean session |

### Pagination

The BO InfoStore API returns results in pages (default 50 items). `bo_client.py` follows pagination links until all WebI documents are enumerated.

### Rate Limiting

Each report requires 3-4 API calls. For 200 reports, that is ~800 requests. The client adds a configurable delay between reports (default 0.2s) to avoid overloading the server.

## JSON Schema

The output JSON mirrors `frd_parsed.json` as closely as possible.

### Top-level Structure

```json
{
  "source": "http://10.17.56.65:8080/biprws",
  "total_reports": 198,
  "extracted_count": 195,
  "error_count": 3,
  "errors": [
    {"id": "12345", "name": "Broken Report", "reason": "403 Forbidden"}
  ],
  "reports": [...]
}
```

### Per-report Object

```json
{
  "folder": "Sales Reports",
  "name": "Daily Sales Summary",
  "report_format": "Paginated",
  "legacy_reports": "Public Folders\\Sales Reports\\Daily Sales Summary",
  "legacy_users": "",
  "summary": "Shows daily sales by retailer",
  "sort": "N/A",
  "target_folder": "Sales Reports",
  "notes": "",
  "datasource_type": "semantic_model",
  "parameters": [
    {
      "label": "Start Date",
      "required": true,
      "select": "Single",
      "notes": ""
    }
  ],
  "filters": [],
  "layout": {
    "main": {
      "columns": ["Retailer No.", "Retailer Name", "City", "Sales Amount"],
      "raw": ""
    }
  },
  "requirements": []
}
```

### Field Mapping

| JSON field | BO Source | Notes |
|---|---|---|
| `name` | `SI_NAME` | |
| `folder` | `SI_PATH` first segment | |
| `legacy_reports` | `SI_PATH` (backslash-joined full path) | Preserves BO folder ancestry |
| `summary` | `SI_DESCRIPTION` | |
| `report_format` | hardcoded `"Paginated"` | All WebI convert to RDL |
| `datasource_type` | universe name keyword match via `config.infer_datasource()` | Reuses pbi.properties keywords |
| `parameters` | `/parameters` endpoint | `mandatory` flag maps to `required` |
| `layout` | `/elements` tables | Tab name = section key, column headers = `columns` |
| `legacy_users` | `""` | Not exposed by REST API |
| `requirements` | `[]` | No BO equivalent |
| `sort` | `"N/A"` | |
| `target_folder` | same as `folder` | Can be overridden in spec |
| `notes` | `""` | |

## Configuration

### New `[bo]` Section in `pbi.properties`

```ini
[bo]
host     = http://10.17.56.65:8080/biprws
username = your.name@ourlotto.com
```

Password is never stored in config — it comes from the environment variable `BO_PASSWORD`, consistent with how `model_generator` handles `SNOWFLAKE_PASSWORD`.

### Existing Sections Reused

- `[datasource_keywords]` — `infer_datasource()` classifies BO reports using the same keyword rules
- `[model_keywords]` — `infer_semantic_model()` selects which PBI semantic model to bind

## CLI Interface

```bash
# Full pipeline (extract + specs)
python convert_bo_reports.py

# Phase 1 only — hit BO API, write bo_extracted.json
python convert_bo_reports.py --only extract

# Phase 2 only — generate specs from existing bo_extracted.json
python convert_bo_reports.py --only specs

# Filter by BO folder
python convert_bo_reports.py --folder "Sales Reports"

# Filter by report name
python convert_bo_reports.py --report "Daily Sales"
```

## Output Layout

```
output/
├── bo-extracted/
│   └── bo_extracted.json      # Phase 1 checkpoint
└── bo-specs/
    └── *.md                   # Phase 2 — ready for Path B (spec_to_rdl.py)
```

## Error Handling

- **Per-report tolerance:** If a single report fails extraction (document locked, permissions denied, corrupt), the tool logs a warning and continues. The `errors` array in the output JSON lists skipped reports with reasons.
- **Session cleanup:** Logon/logoff wrapped in `try/finally` so the session is always cleaned up.
- **Auth failure:** Fails fast with a clear message if logon fails or `BO_PASSWORD` is not set.

## End-to-End User Workflow

```
1. export BO_PASSWORD=...
2. python convert_bo_reports.py --only extract    # hit BO API
3. inspect output/bo-extracted/bo_extracted.json   # sanity check
4. python convert_bo_reports.py --only specs       # generate .md specs
5. edit output/bo-specs/*.md                       # human review
6. python report_generator/spec_to_rdl.py output/bo-specs/  # existing Path B --> .rdl
```
