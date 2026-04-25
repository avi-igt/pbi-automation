# pbi-automation — Command Reference

All commands run from the repo root.

Use the venv Python directly (no activate script):
```bash
alias py=./venv/bin/python   # optional shorthand for this session
```

---

## Tool 1 — report_generator

Converts an FRD Word document into `.rdl` paginated reports, `.pbip` visual reports,
and `.md` spec review documents.

### Scenario A — Full pipeline (FRD → everything)

Parses the FRD, then generates RDL + PBIP + specs in one shot.

```bash
venv/bin/python generate_reports.py
```

Outputs:
- `output/json/frd_parsed.json` — intermediate parsed structure
- `output/rdl/<Section>/<ReportName>.rdl` — paginated reports
- `output/pbip/<Section>/<ReportName>.pbip` — visual report folders
- `output/specs/<report-name>.md` — spec review files

---

### Scenario B — Parse only (FRD → JSON)

Useful to inspect what the parser extracted before generating anything.

```bash
venv/bin/python generate_reports.py --only parse
```

Output: `output/json/frd_parsed.json`

---

### Scenario C — Generate RDL only (JSON → .rdl)

Re-runs just the RDL step without re-parsing the FRD. Requires JSON from a prior parse.

```bash
venv/bin/python generate_reports.py --only rdl
```

Output: `output/rdl/<Section>/<ReportName>.rdl`

---

### Scenario D — Generate PBIP only (JSON → .pbip)

Re-runs just the PBIP step.

```bash
venv/bin/python generate_reports.py --only pbip
```

Output: `output/pbip/<Section>/<ReportName>.Report/` + `.pbip` file

---

### Scenario E — Generate specs only (JSON → .md)

Re-runs just the spec-doc step. Review-ready markdown files.

```bash
venv/bin/python generate_reports.py --only spec
```

Output: `output/specs/<report-name>.md`

---

### Scenario F — Filter by report name

Generate only reports whose name contains the given string (case-insensitive substring).

```bash
# Single report
venv/bin/python generate_reports.py --report "1042 Tax"

# Any report with "Sales" in its name
venv/bin/python generate_reports.py --report "Sales"

# Any report with "Retailer" in its name
venv/bin/python generate_reports.py --report "Retailer"
```

---

### Scenario G — Explicit FRD path

Point to a different FRD file instead of the default (`pbi.properties` → `[paths] frd_docx`).

```bash
venv/bin/python generate_reports.py "TAC Data Examiner Supplemental Document.docx"
```

Combine with filter:
```bash
venv/bin/python generate_reports.py "TAC Data Examiner Supplemental Document.docx" --report "TMIR"
```

---

### Scenario H — Path B: spec-first review workflow

After specs are generated (Scenario E), a reviewer edits the `.md` files in `output/specs/`,
then regenerates reports from the edited specs rather than the raw FRD.

```bash
# Step 1 — generate specs from FRD
venv/bin/python generate_reports.py --only spec

# Step 2 — reviewer edits output/specs/<report-name>.md as needed

# Step 3 — regenerate RDL from reviewed specs
venv/bin/python generate_reports.py --only rdl   # reads from output/specs/ if --from-spec set
# OR directly invoke Path B modules:
venv/bin/python -m report_generator.spec_to_rdl
venv/bin/python -m report_generator.spec_to_pbip
```

Path B output lands in `output/from-spec/rdl/` and `output/from-spec/pbip/`.

---

### Scenario I — SQL override

When a hand-authored SQL file exists for a report, it is used instead of the auto-generated stub.

Existing SQL overrides in `report_generator/sql/`:
```
1042_Tax.sql
1042_Tax_Report.sql
Tax_Withholding.sql
199106-TMIR_Report.sql
Balance Report - Online.sql
Cancelled Validations Overview Report.sql
... (19 total)
```

To add a new override:
1. Create `report_generator/sql/<ExactReportName>.sql`
2. Re-run the relevant step:
```bash
venv/bin/python generate_reports.py --only rdl --report "Cancelled Validations"
```

---

### Scenario J — All-Snowflake FRD (TAC Data Examiner)

The TAC FRD has no DB2 reports — set `default_datasource = snowflake` in `pbi.properties`
before running so unrecognised report names fall through to Snowflake ODBC.

```ini
# pbi.properties
[datasource_keywords]
default_datasource = snowflake
```

```bash
venv/bin/python generate_reports.py "TAC Data Examiner Supplemental Document.docx"
```

---

### Scenario K — Clean generated output

Wipe all output directories to start fresh.

```bash
venv/bin/python clean.py
```

---

## Tool 2 — model_generator

Connects to Snowflake, introspects fact and dimension tables, and generates TMDL
`.SemanticModel` + `.Report` folder pairs ready for deployment to `lpc-v1-app-ldi-pbi-mos`.

### Credentials

**Option 1 — SSO (browser popup, must use native Windows Python in PowerShell):**
```powershell
$env:SNOWFLAKE_USER = "your.name@ourlotto.com"
py generate_models.py
```

**Option 2 — Username/password (works in WSL/bash):**
```bash
export SNOWFLAKE_USER=your_username
export SNOWFLAKE_PASSWORD=your_password
venv/bin/python generate_models.py
```

---

### Scenario L — List all configured models

```bash
venv/bin/python generate_models.py --list
```

Currently configured models:
| Key | Display Name | Fact Table |
|---|---|---|
| `financial_daily` | Financial Daily LDI | `FINANCIAL.FINANCIAL_DAILY` |
| `invoice_detail` | Invoice Detail LDI | `FINANCIAL.INVOICE_DETAIL` |
| `draw_sales` | Draw Sales LDI | `DRAW.DRAW_SALES` |
| `inventory_detail` | Inventory Detail LDI | `INSTANT.INVENTORY_DETAIL` |
| `lvm_daily_bin_sales` | LVM Daily Bin Sales LDI | `LVM.DAILY_BIN_SALES` |
| `lvm_interval_bin_sales` | LVM Interval Bin Sales LDI | `LVM.INTERVAL_BIN_SALES` |
| `promotion_summary` | Promotion Summary LDI | `PROMOTION.PROMOTION_SUMMARY` |
| `order_detail` | Order Detail LDI | `INSTANT.ORDER_DETAILS` |

---

### Scenario M — Generate all models

```bash
export SNOWFLAKE_USER=your_username && export SNOWFLAKE_PASSWORD=your_password
venv/bin/python generate_models.py
```

Output: `output/models/<DisplayName>.SemanticModel/` + `output/models/<DisplayName>.Report/`
for every model in `semantic.properties`.

---

### Scenario N — Generate a single model

```bash
venv/bin/python generate_models.py --model draw_sales
venv/bin/python generate_models.py --model financial_daily
venv/bin/python generate_models.py --model invoice_detail
venv/bin/python generate_models.py --model inventory_detail
venv/bin/python generate_models.py --model lvm_daily_bin_sales
venv/bin/python generate_models.py --model lvm_interval_bin_sales
venv/bin/python generate_models.py --model promotion_summary
venv/bin/python generate_models.py --model order_detail
```

---

### Scenario O — Target a specific environment

Default environment is `d1v1`. Override for dev/cert/prod:

```bash
venv/bin/python generate_models.py --model draw_sales --env d1v1   # dev (default)
venv/bin/python generate_models.py --model draw_sales --env c1v1   # cert
venv/bin/python generate_models.py --model draw_sales --env p1v1   # prod
```

Environment overrides apply Snowflake account/warehouse substitutions from
`[snowflake.<env>]` sections in `semantic.properties`.

---

### Scenario P — Model with non-standard join key (order_detail)

`order_detail` joins Products via `GAME_PRODUCT_KEY` instead of the default `PRODUCT_KEY`.
This is already configured in `semantic.properties`:

```ini
[model.order_detail]
dimensions = dates, products:GAME_PRODUCT_KEY
```

```bash
venv/bin/python generate_models.py --model order_detail
```

The generator emits `fromColumn: GAME_PRODUCT_KEY, toColumn: PRODUCT_KEY` in the
M query merge expression.

---

### Scenario Q — Adding a new model (workflow demo)

1. Add a section to `semantic.properties`:
```ini
[model.my_new_model]
display_name = My New Model LDI
fact_table   = SCHEMA.FACT_TABLE
dimensions   = dates, products, locations
```

2. Generate it:
```bash
venv/bin/python generate_models.py --model my_new_model
```

3. Review output:
```bash
ls output/models/
# → My New Model LDI.SemanticModel/
# → My New Model LDI.Report/
```

4. Copy to deployment repo and open PR:
```bash
cp -r "output/models/My New Model LDI.SemanticModel" \
      "/mnt/c/Users/asingh/git/lpc-v1-app-ldi-pbi-mos/SemanticModels/"
cp -r "output/models/My New Model LDI.Report" \
      "/mnt/c/Users/asingh/git/lpc-v1-app-ldi-pbi-mos/Reports/"
```

---

### Scenario R — Adding a new measure suffix type (no code changes)

Add to `[measure_suffixes]` in `semantic.properties`:

```ini
[measure_suffixes]
_COUNT    = int64,   0
_AMOUNT   = decimal, #,##0.00
_QUANTITY = int64,   #,##0
_UNITS    = int64,   #,##0        ← new: columns ending in _UNITS auto-become measures
```

Re-run any model — the new suffix is picked up automatically.

---

## Tool 3 — bo_converter

Connects to a SAP BusinessObjects server, extracts WebI report metadata (parameters,
layout, SQL queries, folder paths), and generates `.md` spec files + `.rdl` paginated reports.

### Credentials

```bash
export BO_PASSWORD=your_password
```

The username and host are configured in `pbi.properties` under `[bo]`.

---

### Scenario S — Full pipeline (extract + specs + rdl)

```bash
python convert_bo_reports.py
```

Outputs:
- `output/bo-extracted/bo_extracted.json` — extracted metadata
- `output/bo-sql/*.sql` — extracted SQL queries per report
- `output/bo-specs/*.md` — spec review files
- `output/bo-rdl/**/*.rdl` — paginated reports

---

### Scenario T — Extract only (BO API -> JSON + SQL)

```bash
python convert_bo_reports.py --only extract
```

Outputs:
- `output/bo-extracted/bo_extracted.json`
- `output/bo-sql/*.sql`

---

### Scenario U — Generate specs only (JSON -> .md)

Requires JSON from a prior extract.

```bash
python convert_bo_reports.py --only specs
```

Output: `output/bo-specs/*.md`

---

### Scenario V — Generate RDL only (.md -> .rdl)

Requires spec files from a prior specs run.

```bash
python convert_bo_reports.py --only rdl
```

Output: `output/bo-rdl/**/*.rdl`

---

### Scenario W — Filter by folder

Filter extraction to reports under specific BO folders (substring, case-insensitive).

```bash
# Single folder
python convert_bo_reports.py --folder "Connecticut/Reports/CAP"

# Multiple folders (comma-separated)
python convert_bo_reports.py --folder "Connecticut/Reports/CAP, Connecticut/Reports/Finance"

# User folders
python convert_bo_reports.py --folder "Administrator/Julia"
```

The default folder filter is configured in `pbi.properties`:
```ini
[bo]
root_folder = Public Folder/Connecticut/Reports
```

`--folder` overrides the config value. Both support comma-separated lists.

---

### Scenario X — Filter by report name

```bash
python convert_bo_reports.py --report "Daily Sales"
```

Applies to all phases — extract filters documents, specs/rdl filter by filename.

---

### Scenario Y — Custom output directory

```bash
python convert_bo_reports.py -o /tmp/bo-output
```

---

### Scenario Z — Verbose logging

```bash
python convert_bo_reports.py -v
python convert_bo_reports.py --verbose --only extract
```

---

## Quick Reference

| Goal | Command |
|---|---|
| Full FRD pipeline | `venv/bin/python generate_reports.py` |
| Parse FRD only | `venv/bin/python generate_reports.py --only parse` |
| RDL only | `venv/bin/python generate_reports.py --only rdl` |
| PBIP only | `venv/bin/python generate_reports.py --only pbip` |
| Specs only | `venv/bin/python generate_reports.py --only spec` |
| One report | `venv/bin/python generate_reports.py --report "Name"` |
| Different FRD | `venv/bin/python generate_reports.py path/to/FRD.docx` |
| Clean outputs | `venv/bin/python clean.py` |
| List models | `venv/bin/python generate_models.py --list` |
| All models | `venv/bin/python generate_models.py` |
| One model | `venv/bin/python generate_models.py --model <key>` |
| Target env | `venv/bin/python generate_models.py --model <key> --env c1v1` |
| BO full pipeline | `python convert_bo_reports.py` |
| BO extract only | `python convert_bo_reports.py --only extract` |
| BO specs only | `python convert_bo_reports.py --only specs` |
| BO RDL only | `python convert_bo_reports.py --only rdl` |
| BO filter folder | `python convert_bo_reports.py --folder "CAP, Finance"` |
| BO filter report | `python convert_bo_reports.py --report "Daily Sales"` |
