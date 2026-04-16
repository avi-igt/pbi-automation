# Handbook Impact on pbi-automation

Review of _Power BI Developer Handbook & Guide_ (Brightstar, 2026) against the pbi-automation toolchain.

---

## Already Compliant

| Handbook Rule | pbi-automation Status |
|---|---|
| PBIP only (PBIX prohibited in Git) | `pbip_generator.py` generates PBIP folder structures only |
| Paginated → Power BI Report Builder / RDL | `rdl_generator.py` generates RDL; keyword detection logic matches the handbook's tool selection decision tree exactly |
| Interactive/analytical → Power BI Desktop | `pbip_generator.py` binds via `definition.pbir` byPath to semantic model — Lane 1 compliant |
| Snowflake ODBC approved only for Lane 3 (paginated) | `sfodbc_dsn` is used only in RDL generation; PBIP reports bind to semantic models, not ODBC |
| DB2 ODBC approved for Lane 3 | `db2_dsn` is used only in RDL generation — correct |

---

## Gaps & Required Changes

### 1. Semantic Model Names Will Break (Section 1.1)

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

### 2. No Native Snowflake Connector Config (Section 3.5.3)

The handbook mandates ADBC 2.0 native connector for all Lane 1/2 (semantic model / interactive) workloads and explicitly deprecates ODBC for semantic models:

> _ODBC usage is deprecated for semantic models and will be phased out in favour of native connectors._

Specified connection:
```
Host:           igtgloballottery-igtpxv1_ldi.privatelink.snowflakecomputing.com
Implementation: 2.0  (Arrow-based ADBC)
```

pbi-automation does not currently generate any direct Snowflake PBIP connections (all visual reports bind to semantic models), so there is no active violation. However, there is no config path for native connector usage if the requirement arises.

**Action**: Add a `[snowflake_native]` section to `pbi.properties` now as a placeholder:

```ini
[snowflake_native]
host           = igtgloballottery-igtpxv1_ldi.privatelink.snowflakecomputing.com
implementation = 2.0
```

This keeps the connection detail out of generator code and in the config layer where it belongs.

---

### 3. Branching Strategy Not Adopted (Section 6)

The handbook defines:

```
main    → Production
develop → Integration
feature/<ticket>-description
```

pbi-automation currently commits everything directly to `main`.

**Action**: Adopt `develop` as the integration branch. Use `feature/` branches for work items going forward.

---

### 4. Power Query Naming (Future — Section 1.4)

Not currently applicable. `pbip_generator.py` only generates semantic model bindings; it does not produce any Power Query / M code.

If M query generation is added in future, the required conventions are:

| Object | Convention | Example |
|---|---|---|
| Source query | `_Src_<Source>_<Domain>`, hidden, load-disabled | `_Src_Snowflake_Sales` |
| Staging / helper | `_Stg<Domain>`, hidden, load-disabled | `_StgSales` |
| Applied step | Verb-based PascalCase | `FilteredActiveRows` |
| Folding break | `NonFoldable_<Description>` (requires PR justification) | `NonFoldable_Pivot` |

---

## Priority Summary

| Priority | Action |
|---|---|
| High | Confirm model rename timeline with architect; ensure `pbi.properties` is the only change point when Fabric model names change |
| Medium | Add `[snowflake_native]` section to `pbi.properties` (future-proofing for native ADBC connector) |
| Low | Adopt `develop` branching strategy |
| Future | Apply Power Query naming conventions if M query generation is added |

The tool's architectural approach is sound. The primary risk is a Fabric model rename cascading through `pbi.properties` if it is not tracked carefully.
