# Handbook Impact on pbi-automation

Review of _Power BI Architecture, Standards & Governance_ (Brightstar, 2026) against the pbi-automation toolchain.

---

## Already Compliant

| Handbook Rule | pbi-automation Status |
|---|---|
| PBIP only (PBIX prohibited in Git) | `pbip_generator.py` generates PBIP folder structures only |
| Semantic models in TMDL format | `model_generator` produces `.SemanticModel` TMDL folder pairs |
| Paginated → Power BI Report Builder / RDL | `rdl_generator.py` generates RDL; keyword detection logic matches the handbook's tool selection decision tree |
| Interactive/analytical → Power BI Desktop | `pbip_generator.py` binds via `definition.pbir` byPath to semantic model — Lane 1 compliant |
| Snowflake ODBC approved only for Lane 3 (paginated) | `sfodbc_dsn` is used only in RDL generation; PBIP reports bind to semantic models, not ODBC |
| DB2 ODBC approved for Lane 3 | `db2_dsn` is used only in RDL generation — correct |
| Snowflake ADBC 2.0 native connector | `[snowflake_native]` section exists in `pbi.properties` with correct host and `implementation = 2.0`; `model_generator` embeds `Implementation = "2.0"` in every generated M query `Source` step |

---

## Gaps & Required Changes

### 1. Semantic Model Names Will Break (Naming Conventions — Semantic Model Naming)

The handbook mandates: **Title Case + mandatory postfix (LDI / RSM / RPT)**. Current `pbi.properties`:

```ini
MO_Sales, MO_DrawData, MO_CoreTables ...
```

Compliant form would be: `MO Sales LDI`, `MO Draw Data LDI`, etc.

When Fabric models are renamed to comply, the following will all break:
- Every `[model_keywords]` key in `pbi.properties`
- Every `[datasets]` key in `pbi.properties`
- Every generated `definition.pbir` byPath reference (e.g., `../MO_Sales.SemanticModel`)

**Action**: Confirm with the architect whether existing models will be renamed and on what timeline. If yes, `pbi.properties` is the single change point — that is the correct design. No generator code changes needed, only config.

---

### 2. Power Query Applied Step Naming — ACTIVE (Power Query (M) Naming Standards)

The handbook requires verb-based PascalCase for applied steps (no spaces, no default names). The
`model_generator` currently generates non-compliant step names in every fact table M query
(`model_generator/tmdl_builder.py`, lines ~289, 298–299):

| Generated step name | Handbook verdict | Required name |
|---|---|---|
| `#"Filtered Rows"` | "Avoid" — default Power BI name | `FilteredByDateRange` or similar |
| `#"Merged Dates"` | Quoted identifier (space) — not PascalCase | `MergedDates` |
| `#"Expanded Dates"` | Quoted identifier (space) — not PascalCase | `ExpandedDates` |

The `Source`, `DB`, `Schema`, `FactTable` step names are implementation-internal and acceptable as
they are not user-visible in the fields pane.

**Action**: Update `tmdl_builder.py` to generate compliant step names:
- `"Filtered Rows"` → `f"FilteredByDateRange"` (or the actual column name, e.g. `f"FilteredBy{filter_column.title().replace('_', '')}"`)
- `f"Merged {dim_spec.table_name}"` → `f"Merged{dim_spec.table_name.replace(' ', '')}"` (PascalCase, no spaces)
- `f"Expanded {dim_spec.table_name}"` → `f"Expanded{dim_spec.table_name.replace(' ', '')}"` (PascalCase, no spaces)

This is a code change, not a config change. Low risk; no output format change, only step labels.

---

### 3. Paginated Report Deployment Workflow (Version Control & CI/CD — Paginated Reports)

The handbook introduces an explicit sequencing constraint not previously documented:

> _"Publish/upload the paginated report to the service and then use git. Paginated reports don't render if you start with the files in git."_

Additional constraints:
- **Deleting**: Delete the entire report folder from git — not just the `.rdl` file.
- **Renaming**: Cannot rename an `.rdl` in git. Must delete the folder and recreate it with the new name.

`report_generator` writes `.rdl` files to `output/rdl/`. These are then manually copied into
`lpc-v1-app-ldi-pbi-mos`. The workflow must be:

```
report_generator → output/rdl/  →  publish to Power BI Service  →  then commit to lpc-v1-app-ldi-pbi-mos
```

**Action**: Update the deployment section of the README / deployment runbook for
`lpc-v1-app-ldi-pbi-mos` to make this order explicit. No code changes needed in pbi-automation.

---

### 4. Branching Strategy Not Adopted (Version Control & CI/CD — Branching Strategy)

The handbook defines a single-repo, multi-site branching model:

```
lpc-v1-app-ldi-pbi  (single repo, all sites)
  lpcv1-develop           ← product base branch
    lpcv1xx-develop-yyyy.mm  ← delivery cycle branches off product base
  sssv1-develop           ← per-site main (e.g. mosv1-develop)
    sssv1xx-develop-MM.mm    ← per-site delivery cycle branches
```

pbi-automation currently commits everything directly to `main`. The deployment target
(`lpc-v1-app-ldi-pbi-mos`) is the repo that must adopt this structure; pbi-automation itself is a
generation tool and its branching is separate.

**Action**: Adopt `develop` as the integration branch in `lpc-v1-app-ldi-pbi-mos`. Use delivery
cycle branches (`mosv1xx-develop-yyyy.mm`) going forward. For pbi-automation itself, consider
whether `develop` branching is warranted given it is a tooling repo.

---

## Priority Summary

| Priority | Action |
|---|---|
| High | Confirm model rename timeline with architect; `pbi.properties` is the only change point when Fabric model names change |
| High | Fix Power Query applied step naming in `model_generator/tmdl_builder.py` — `#"Filtered Rows"`, `#"Merged X"`, `#"Expanded X"` are non-compliant |
| Medium | Document paginated report deployment order in lpc-v1-app-ldi-pbi-mos deployment runbook: publish to service first, then git |
| Low | Adopt `develop` branching strategy in `lpc-v1-app-ldi-pbi-mos` |

The tool's architectural approach remains sound. Snowflake ADBC 2.0 compliance (previous Gap 2) is
resolved. The primary active code gap is Power Query step naming in `model_generator`.
