"""
tmdl_builder.py — builds all TMDL and supporting file content as strings.

All functions return strings. No file I/O here — writing is handled by
model_generator.py.

TMDL uses TAB indentation throughout.
"""

import json
import re
import uuid
from dataclasses import dataclass, field

import yaml

from model_generator.config import DimensionDef, MeasureSuffix, ModelDef, SnowflakeConfig
from model_generator.snowflake_client import ColumnInfo, sf_type_to_tmdl

_DIMENSIONS_DIR = __import__("pathlib").Path(__file__).parent / "dimensions"


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def to_title(col_name: str) -> str:
    """SNAKE_CASE → 'Title Case Name'.

    SALES_COUNT                    → 'Sales Count'
    PLAYER_CARD_ONLINE_SALES_COUNT → 'Player Card Online Sales Count'
    """
    return " ".join(w.capitalize() for w in col_name.lower().split("_"))


def is_all_uppercase(name: str) -> bool:
    """Return True for ALL_UPPERCASE_WITH_UNDERSCORES identifiers."""
    return bool(re.match(r"^[A-Z][A-Z0-9_]*$", name))


def new_tag() -> str:
    """Return a fresh UUID string for a lineageTag."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Column classification
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedColumn:
    info: ColumnInfo
    kind: str       # "key" | suffix string (e.g. "_COUNT") | "visible"
    tmdl_type: str  # TMDL dataType


def classify_columns(
    columns: list[ColumnInfo],
    measure_suffixes: list[MeasureSuffix],
) -> list[ClassifiedColumn]:
    """Classify each fact table column for the merged-queries model.

    Rules (applied in order):
    1. Ends with _KEY                      → "key" (hidden int64)
    2. Ends in a configured measure suffix → suffix string used as kind
    3. Everything else                     → "visible"
    """
    result = []
    for col in columns:
        name = col.name
        if name.endswith("_KEY"):
            kind = "key"
            tmdl_type = "int64"
        else:
            matched = next((ms for ms in measure_suffixes if name.endswith(ms.suffix)), None)
            if matched:
                kind = matched.suffix
                tmdl_type = matched.tmdl_type
            else:
                kind = "visible"
                tmdl_type = sf_type_to_tmdl(col.sf_type, col.numeric_scale)
        result.append(ClassifiedColumn(info=col, kind=kind, tmdl_type=tmdl_type))
    return result


# ---------------------------------------------------------------------------
# Dimension merge specification
# ---------------------------------------------------------------------------

@dataclass
class DimMergeSpec:
    alias: str                          # e.g. "dates"
    table_name: str                     # PQ query name, e.g. "Dates"
    fact_key: str                       # join column in fact table, e.g. "DATE_KEY"
    dim_key: str                        # join column in dim table, e.g. "DATE_KEY"
    # (dim_source_col, output_name_in_fact, tmdl_type)
    visible_cols: list[tuple[str, str, str]] = field(default_factory=list)


def _load_strategy_a(dim_def: DimensionDef) -> dict[str, str]:
    """Load visible_columns from dimensions/<alias>.yaml.

    Returns dict of {COLUMN_NAME: display_name}.
    Returns empty dict (with warning) if no usable YAML file is found.
    """
    import sys

    yaml_path = _DIMENSIONS_DIR / f"{dim_def.alias}.yaml"

    if not yaml_path.exists() and dim_def.inherit:
        inherited_path = _DIMENSIONS_DIR / f"{dim_def.inherit}.yaml"
        if inherited_path.exists():
            yaml_path = inherited_path
        else:
            print(
                f"  WARNING: dimensions/{dim_def.alias}.yaml not found and "
                f"inherited dimensions/{dim_def.inherit}.yaml also not found. "
                f"All columns in {dim_def.source} will be hidden.",
                file=sys.stderr,
            )
            return {}

    if not yaml_path.exists():
        print(
            f"  WARNING: dimensions/{dim_def.alias}.yaml not found for Strategy A. "
            f"All columns in {dim_def.source} will be hidden. "
            f"Create the YAML to control visibility.",
            file=sys.stderr,
        )
        return {}

    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    raw = data.get("visible_columns", {})
    return {k.upper(): str(v) for k, v in raw.items()}


def build_dim_merge_spec(
    dim_def: DimensionDef,
    columns: list[ColumnInfo],
    fact_key: str,
) -> DimMergeSpec:
    """Build a DimMergeSpec describing how to join and expand a dimension.

    fact_key: the column name in the fact table used for the join
              (may differ from dim_def.primary_key for role-playing dims).
    """
    table_name = to_title(dim_def.alias)
    col_type_map = {col.name: sf_type_to_tmdl(col.sf_type, col.numeric_scale) for col in columns}

    if dim_def.strategy == "A":
        visible_map = _load_strategy_a(dim_def)
        visible_cols = [
            (src_col, display_name, col_type_map.get(src_col, "string"))
            for src_col, display_name in visible_map.items()
        ]
    else:
        # Strategy B: include all columns except the primary key; derive display
        # names via to_title().  Works for ALL_UPPERCASE Snowflake schemas too.
        visible_cols = [
            (col.name, to_title(col.name), sf_type_to_tmdl(col.sf_type, col.numeric_scale))
            for col in columns
            if col.name != dim_def.primary_key
        ]

    return DimMergeSpec(
        alias=dim_def.alias,
        table_name=table_name,
        fact_key=fact_key,
        dim_key=dim_def.primary_key,
        visible_cols=visible_cols,
    )


# ---------------------------------------------------------------------------
# TMDL fragment builders — columns and measures
# ---------------------------------------------------------------------------

def _col_block(
    col_name: str,
    data_type: str,
    hidden: bool,
    summarize_by: str = "none",
    display_name: str | None = None,
    display_folder: str | None = None,
) -> str:
    """Render a TMDL column block.

    The TMDL column identifier is the display name (quoted when it contains
    spaces). sourceColumn always points to the physical/PQ column name.
    """
    tmdl_id = display_name if (display_name and display_name != col_name) else col_name
    if " " in tmdl_id or "'" in tmdl_id:
        tmdl_ref = "'" + tmdl_id.replace("'", "''") + "'"
    else:
        tmdl_ref = tmdl_id

    lines = [f"\tcolumn {tmdl_ref}"]
    lines.append(f"\t\tdataType: {data_type}")
    if hidden:
        lines.append("\t\tisHidden")
    if display_folder:
        lines.append(f"\t\tdisplayFolder: {display_folder}")
    lines.append(f"\t\tsummarizeBy: {summarize_by}")
    lines.append(f"\t\tsourceColumn: {col_name}")
    lines.append(f"\t\tlineageTag: {new_tag()}")
    lines.append("")
    lines.append("\t\tannotation SummarizationSetBy = Automatic")
    return "\n".join(lines)


def _measure_block(
    measure_name: str,
    table_name: str,
    col_name: str,
    fmt: str,
    display_folder: str = "Base Measures",
) -> str:
    """Render a TMDL measure block."""
    return (
        f"\tmeasure '{measure_name}' = CALCULATE(SUM('{table_name}'[{col_name}]))\n"
        f"\t\tformatString: \"{fmt}\"\n"
        f"\t\tdisplayFolder: \"{display_folder}\"\n"
        f"\t\tlineageTag: {new_tag()}"
    )


# ---------------------------------------------------------------------------
# M query templates
# ---------------------------------------------------------------------------

def _m_query(schema: str, obj_name: str, obj_kind: str, mode: str) -> str:
    """Render a simple M query partition block (no merges).

    Used for standalone dimension tables.
    """
    return (
        f"\tpartition '{obj_name}' = m\n"
        f"\t\tmode: {mode}\n"
        f"\t\tsource = ```\n"
        f"\t\t\t\tlet\n"
        f"\t\t\t\t\tSource = Snowflake.Databases(\n"
        f"\t\t\t\t\t\t#\"SnowflakeServer\",\n"
        f"\t\t\t\t\t\t#\"SnowflakeWarehouse\",\n"
        f"\t\t\t\t\t\t[Role = #\"SnowflakeRole\", Implementation = \"2.0\"]),\n"
        f"\t\t\t\t\tDB = Source{{[Name = #\"SnowflakeDBName\", Kind = \"Database\"]}}[Data],\n"
        f"\t\t\t\t\tSchema = DB{{[Name = \"{schema}\", Kind = \"Schema\"]}}[Data],\n"
        f"\t\t\t\t\tResult = Schema{{[Name = \"{obj_name}\", Kind = \"{obj_kind}\"]}}[Data]\n"
        f"\t\t\t\tin\n"
        f"\t\t\t\t\tResult\n"
        f"\t\t\t\t```"
    )


def _m_query_fact(
    schema: str,
    obj_name: str,
    obj_kind: str,
    dim_specs: list[DimMergeSpec],
    filter_column: str | None,
) -> str:
    """Render the M query partition for the fact table.

    Builds an import-mode query with:
    - Optional filtered rows step (RangeStart/RangeEnd)
    - NestedJoin + ExpandTableColumn steps for each dimension
    """
    T = "\t\t\t\t"   # 4 tabs: let/in/closing ```
    S = T + "\t"     # 5 tabs: let step bindings

    steps: list[str] = []

    steps.append(
        f"{S}Source = Snowflake.Databases("
        f"#\"SnowflakeServer\", #\"SnowflakeWarehouse\", "
        f"[Role = #\"SnowflakeRole\", Implementation = \"2.0\"])"
    )
    steps.append(
        f"{S}DB = Source{{[Name = #\"SnowflakeDBName\", Kind = \"Database\"]}}[Data]"
    )
    steps.append(
        f"{S}Schema = DB{{[Name = \"{schema}\", Kind = \"Schema\"]}}[Data]"
    )
    steps.append(
        f"{S}FactTable = Schema{{[Name = \"{obj_name}\", Kind = \"{obj_kind}\"]}}[Data]"
    )

    prev = "FactTable"

    if filter_column:
        steps.append(
            f"{S}FilteredByDateRange = Table.SelectRows({prev}, "
            f"each [{filter_column}] >= RangeStart and [{filter_column}] < RangeEnd)"
        )
        prev = "FilteredByDateRange"

    for dim_spec in dim_specs:
        if not dim_spec.visible_cols:
            continue  # skip dimensions with no visible columns to expand

        merge_step = f"Merged{dim_spec.table_name.replace(' ', '')}"
        expand_step = f"Expanded{dim_spec.table_name.replace(' ', '')}"

        dim_ref = f'#"{dim_spec.table_name}"' if " " in dim_spec.table_name else dim_spec.table_name
        steps.append(
            f"{S}{merge_step} = Table.NestedJoin({prev}, "
            f"{{\"{dim_spec.fact_key}\"}}, "
            f"{dim_ref}, "
            f"{{\"{dim_spec.dim_key}\"}}, "
            f"\"{dim_spec.table_name}\", JoinKind.LeftOuter)"
        )
        prev = merge_step

        src_cols = ", ".join(f"\"{c[0]}\"" for c in dim_spec.visible_cols)
        out_cols = ", ".join(f"\"{c[1]}\"" for c in dim_spec.visible_cols)
        steps.append(
            f"{S}{expand_step} = Table.ExpandTableColumn("
            f"{prev}, \"{dim_spec.table_name}\", {{{src_cols}}}, {{{out_cols}}})"
        )
        prev = expand_step

    steps_str = ",\n".join(steps)

    return (
        f"\tpartition '{obj_name}' = m\n"
        f"\t\tmode: import\n"
        f"\t\tsource = ```\n"
        f"{T}let\n"
        f"{steps_str}\n"
        f"{T}in\n"
        f"{S}{prev}\n"
        f"{T}```"
    )


# ---------------------------------------------------------------------------
# Cross-dimension name collision resolution
# ---------------------------------------------------------------------------

def _resolve_dim_name_collisions(dim_specs: list[DimMergeSpec]) -> list[DimMergeSpec]:
    """Ensure output_names are globally unique across all dimension merge specs.

    When the same output_name appears in two or more dim_specs, every occurrence
    is prefixed with that spec's table_name to disambiguate.

    Example:
        products.yaml and locations.yaml both map SETTLE_CLASS_CODE →
        'Settle Class Code'.  After resolution:
          Products dim  → 'Products Settle Class Code'
          Locations dim → 'Locations Settle Class Code'

    The resolved names are used consistently in both the M query
    ExpandTableColumn step and the TMDL column declarations.
    """
    from collections import Counter

    # Count how many distinct dim_specs each output_name appears in
    name_count: Counter[str] = Counter()
    for ds in dim_specs:
        for _, output_name, _ in ds.visible_cols:
            name_count[output_name] += 1

    # Rebuild specs, prefixing colliding names with the dimension table name
    resolved: list[DimMergeSpec] = []
    for ds in dim_specs:
        new_cols = []
        for (src_col, output_name, tmdl_type) in ds.visible_cols:
            if name_count[output_name] > 1:
                output_name = f"{ds.table_name} {output_name}"
            new_cols.append((src_col, output_name, tmdl_type))
        resolved.append(DimMergeSpec(
            alias=ds.alias,
            table_name=ds.table_name,
            fact_key=ds.fact_key,
            dim_key=ds.dim_key,
            visible_cols=new_cols,
        ))

    return resolved


# ---------------------------------------------------------------------------
# Fact table TMDL
# ---------------------------------------------------------------------------

def build_fact_table_tmdl(
    model_def: ModelDef,
    columns: list[ColumnInfo],
    obj_kind: str,
    measure_suffixes: list[MeasureSuffix],
    dim_specs: list[DimMergeSpec] | None = None,
    filter_column: str | None = None,
) -> str:
    """Generate the full TMDL for the fact table.

    Columns ending with _KEY are hidden. Columns ending with a configured
    measure suffix become hidden source columns with a DAX measure. All
    remaining fact columns are visible. Dimension columns from merged
    queries are appended with a per-dimension display folder.
    """
    if dim_specs is None:
        dim_specs = []

    # Resolve any cross-dimension output name collisions before generating
    # both the M query ExpandTableColumn steps and the TMDL column blocks.
    dim_specs = _resolve_dim_name_collisions(dim_specs)

    table_name      = model_def.display_name.rsplit(" ", 1)[0]
    fact_dims_folder = f"{table_name} Dims"      # e.g. "Draw Sales Dims"
    measures_folder  = f"{table_name} Measures"  # e.g. "Draw Sales Measures"
    classified = classify_columns(columns, measure_suffixes)

    # Collect resolved dim output names so visible fact columns can avoid collisions.
    # A fact column whose Title Case name collides with a dim output name is prefixed
    # with "Fact " (e.g. CALENDAR_YEAR → "Fact Calendar Year" when the Dates dim
    # already exposes a column named "Calendar Year").
    _dim_output_names: set[str] = {
        output_name
        for ds in dim_specs
        for _, output_name, _ in ds.visible_cols
    }

    def _fact_display_name(col_name: str) -> str:
        tentative = to_title(col_name)
        return f"Fact {tentative}" if tentative in _dim_output_names else tentative

    lines = [
        f"table '{table_name}'",
        f"\tlineageTag: {new_tag()}",
        "",
        _m_query_fact(model_def.fact_schema, model_def.fact_table, obj_kind, dim_specs, filter_column),
        "",
    ]

    # Hidden key columns
    for cc in classified:
        if cc.kind == "key":
            lines.append(_col_block(cc.info.name, cc.tmdl_type, hidden=True))

    # Hidden measure source columns — grouped in "<TableName> Measures" folder
    for ms in measure_suffixes:
        suffix_cols = [cc for cc in classified if cc.kind == ms.suffix]
        for cc in suffix_cols:
            lines.append(_col_block(
                cc.info.name, cc.tmdl_type, hidden=True,
                display_folder=measures_folder,
            ))

    # Visible fact-own columns — grouped in "<TableName> Dims" folder, renamed to Title Case.
    # If the Title Case name collides with a dimension output name, prefix with "Fact ".
    for cc in classified:
        if cc.kind == "visible":
            lines.append(_col_block(
                cc.info.name, cc.tmdl_type, hidden=False,
                summarize_by="none",
                display_name=_fact_display_name(cc.info.name),
                display_folder=fact_dims_folder,
            ))

    # Dimension columns (from merged queries), grouped by dimension
    for dim_spec in dim_specs:
        if not dim_spec.visible_cols:
            continue
        dim_folder = to_title(dim_spec.alias)
        for (_, output_name, tmdl_type) in dim_spec.visible_cols:
            lines.append(_col_block(
                output_name, tmdl_type, hidden=False,
                summarize_by="none",
                display_folder=dim_folder,
            ))

    # DAX measures — one per measure-suffix column, grouped in "<TableName> Measures" folder
    for ms in measure_suffixes:
        suffix_cols = [cc for cc in classified if cc.kind == ms.suffix]
        for cc in suffix_cols:
            measure_name = to_title(cc.info.name)
            lines.append(_measure_block(measure_name, table_name, cc.info.name, ms.fmt,
                                        display_folder=measures_folder))
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dimension table TMDL
# ---------------------------------------------------------------------------

def build_dimension_tmdl(
    dim_def: DimensionDef,
    columns: list[ColumnInfo],
) -> str:
    """Generate the TMDL for a dimension staging table.

    Dimension tables are hidden in the model view — they exist only to
    support the NestedJoin in the fact table's M query. All columns are
    written as-is with their Snowflake types; visibility is controlled
    by the fact table's expand step.
    """
    table_name = to_title(dim_def.alias)

    lines = [
        f"table '{table_name}'",
        f"\tisHidden",
        f"\tlineageTag: {new_tag()}",
        "",
        _m_query(dim_def.schema, dim_def.table, "Table", "import"),
        "",
        _col_block(dim_def.primary_key, "int64", hidden=False),
    ]

    for col in columns:
        if col.name == dim_def.primary_key:
            continue
        tmdl_type = sf_type_to_tmdl(col.sf_type, col.numeric_scale)
        lines.append(_col_block(col.name, tmdl_type, hidden=False))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# relationships.tmdl  (empty — relationships replaced by merged queries)
# ---------------------------------------------------------------------------

def build_relationships_tmdl(
    model_def: ModelDef,
    fact_column_names: set[str],
    dim_defs: dict[str, DimensionDef],
) -> str:
    """No TMDL relationships are generated; dimensions are joined via M query."""
    return ""


# ---------------------------------------------------------------------------
# expressions.tmdl
# ---------------------------------------------------------------------------

def build_expressions_tmdl(
    sf_config: SnowflakeConfig,
    has_date_filter: bool = False,
) -> str:
    """Generate expressions.tmdl with Snowflake connection parameters.

    When has_date_filter is True, RangeStart and RangeEnd datetime
    parameters are added for incremental refresh support.
    """

    def _param(name: str, value: str) -> str:
        return (
            f"expression {name} = \"{value}\" "
            f"meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]\n"
            f"\tlineageTag: {new_tag()}\n"
            f"\n"
            f"\tannotation PBI_ResultType = Text\n"
        )

    def _datetime_param(name: str, default_value: str) -> str:
        return (
            f"expression {name} = {default_value} "
            f"meta [IsParameterQuery=true, Type=\"DateTime\", IsParameterQueryRequired=true]\n"
            f"\tlineageTag: {new_tag()}\n"
            f"\n"
            f"\tannotation PBI_ResultType = DateTime\n"
        )

    server = f"{sf_config.account}.snowflakecomputing.com"

    parts = [
        _param("SnowflakeServer", server),
        _param("SnowflakeWarehouse", sf_config.warehouse),
        _param("SnowflakeRole", sf_config.role),
        _param("SnowflakeDBName", sf_config.database),
    ]

    if has_date_filter:
        parts.append(_datetime_param("RangeStart", "#datetime(2020, 1, 1, 0, 0, 0)"))
        parts.append(_datetime_param("RangeEnd", "#datetime(2030, 1, 1, 0, 0, 0)"))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# model.tmdl
# ---------------------------------------------------------------------------

def _tmdl_table_ref(name: str) -> str:
    """Return a TMDL table reference — quoted only if the name contains spaces."""
    return f"'{name}'" if " " in name else name


def build_model_tmdl(model_def: ModelDef, dim_defs: dict[str, DimensionDef]) -> str:
    """Generate model.tmdl.

    ref table declarations must be at the root level of the file (no indent),
    not nested inside the model Model block.  Single-word names are unquoted;
    multi-word names are single-quoted.
    """
    table_name = model_def.display_name.rsplit(" ", 1)[0]
    dim_table_names = [to_title(a) for a in model_def.dimensions]

    all_tables = dim_table_names + [table_name]
    ref_lines = "\n".join(f"ref table {_tmdl_table_ref(n)}" for n in all_tables)

    return (
        f"model Model\n"
        f"\tculture: en-US\n"
        f"\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        f"\n"
        f"{ref_lines}\n"
    )


# ---------------------------------------------------------------------------
# database.tmdl
# ---------------------------------------------------------------------------

def build_database_tmdl() -> str:
    return "database\n\tcompatibilityLevel: 1600\n"


# ---------------------------------------------------------------------------
# .platform (JSON)
# ---------------------------------------------------------------------------

def build_platform_json(model_def: ModelDef) -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/"
            "gitIntegration/platformProperties/2.0.0/schema.json"
        ),
        "metadata": {
            "type": "SemanticModel",
            "displayName": model_def.display_name,
        },
        "config": {
            "version": "2.0",
            "logicalId": new_tag(),
        },
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition.pbism (JSON)
# ---------------------------------------------------------------------------

def build_definition_pbism() -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "semanticModel/definitionProperties/1.0.0/schema.json"
        ),
        "version": "4.2",
        "settings": {},
    }
    return json.dumps(payload, indent=2)
