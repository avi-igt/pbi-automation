"""
tmdl_builder.py — builds all TMDL and supporting file content as strings.

All functions return strings. No file I/O here — writing is handled by
model_generator.py.

TMDL uses TAB indentation throughout.
"""

import json
import re
import uuid
from dataclasses import dataclass

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
    kind: str       # "count" | "amount" | "key" | "hidden" | "visible"
    tmdl_type: str  # TMDL dataType


def classify_columns(
    columns: list[ColumnInfo],
    dim_primary_keys: set[str],
    measure_suffixes: list[MeasureSuffix],
) -> list[ClassifiedColumn]:
    """Classify each column according to the star schema rules.

    Rules (applied in order):
    1. Exact match on a dimension join key  → "key"
    2. Ends in a configured measure suffix  → suffix string used as kind (e.g. "_COUNT")
    3. ALL_UPPERCASE, no suffix match       → "hidden"
    4. Anything else (Title Case / mixed)   → "visible"

    Measure suffixes and their types/formats are configured in [measure_suffixes]
    in semantic.properties.
    """
    result = []
    for col in columns:
        name = col.name
        if name in dim_primary_keys:
            kind = "key"
            tmdl_type = "int64"
        else:
            matched = next((ms for ms in measure_suffixes if name.endswith(ms.suffix)), None)
            if matched:
                kind = matched.suffix       # e.g. "_COUNT", "_AMOUNT", "_QUANTITY"
                tmdl_type = matched.tmdl_type
            elif is_all_uppercase(name):
                kind = "hidden"
                tmdl_type = sf_type_to_tmdl(col.sf_type, col.numeric_scale)
            else:
                kind = "visible"
                tmdl_type = sf_type_to_tmdl(col.sf_type, col.numeric_scale)
        result.append(ClassifiedColumn(info=col, kind=kind, tmdl_type=tmdl_type))
    return result


# ---------------------------------------------------------------------------
# TMDL fragment builders — columns
# ---------------------------------------------------------------------------

def _col_block(
    col_name: str,
    data_type: str,
    hidden: bool,
    summarize_by: str = "none",
    display_name: str | None = None,
) -> str:
    """Render a TMDL column block."""
    lines = [f"\tcolumn {col_name}"]
    lines.append(f"\t\tdataType: {data_type}")
    if hidden:
        lines.append("\t\tisHidden")
    if display_name and display_name != col_name:
        lines.append(f"\t\tname: {display_name}")
    lines.append(f"\t\tsummarizeBy: {summarize_by}")
    lines.append(f"\t\tsourceColumn: {col_name}")
    lines.append(f"\t\tlineageTag: \"{new_tag()}\"")
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
        f"\t\tlineageTag: \"{new_tag()}\""
    )


# ---------------------------------------------------------------------------
# M query template
# ---------------------------------------------------------------------------

def _m_query(schema: str, obj_name: str, obj_kind: str, mode: str) -> str:
    """Render the M query partition block for a table."""
    return (
        f"\tpartition '{obj_name}'\n"
        f"\t\tmode: {mode}\n"
        f"\t\tsource\n"
        f"\t\t\ttype: m\n"
        f"\t\t\texpression = ```\n"
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
        f"\t\t\t```"
    )


# ---------------------------------------------------------------------------
# Fact table TMDL
# ---------------------------------------------------------------------------

def build_fact_table_tmdl(
    model_def: ModelDef,
    columns: list[ColumnInfo],
    dim_primary_keys: set[str],
    obj_kind: str,
    measure_suffixes: list[MeasureSuffix],
) -> str:
    """Generate the full TMDL for the fact table (columns + measures).

    Measure suffixes drive which columns become hidden source columns with
    corresponding DAX measures. Configured via [measure_suffixes] in
    semantic.properties.
    """
    table_name = model_def.display_name.rsplit(" ", 1)[0]
    classified = classify_columns(columns, dim_primary_keys, measure_suffixes)

    lines = [
        f"table '{table_name}'",
        f"\tlineageTag: \"{new_tag()}\"",
        "",
        _m_query(model_def.fact_schema, model_def.fact_table, obj_kind, "directQuery"),
        "",
        "\t// --- KEY COLUMNS (hidden — relationship use only) ---",
    ]

    for cc in classified:
        if cc.kind == "key":
            lines.append(_col_block(cc.info.name, cc.tmdl_type, hidden=True))

    lines += ["", "\t// --- OTHER HIDDEN COLUMNS ---"]
    for cc in classified:
        if cc.kind == "hidden":
            lines.append(_col_block(cc.info.name, cc.tmdl_type, hidden=True))

    # One source-column section per configured measure suffix
    for ms in measure_suffixes:
        label = ms.suffix.lstrip("_")
        suffix_cols = [cc for cc in classified if cc.kind == ms.suffix]
        lines += ["", f"\t// --- {label} COLUMNS (hidden, summarizeBy: none) ---"]
        for cc in suffix_cols:
            lines.append(_col_block(cc.info.name, cc.tmdl_type, hidden=True))

    lines += ["", "\t// --- VISIBLE COLUMNS ---"]
    for cc in classified:
        if cc.kind == "visible":
            lines.append(_col_block(cc.info.name, cc.tmdl_type, hidden=False,
                                    summarize_by="none"))

    # One measure section per configured suffix (only if columns exist)
    for ms in measure_suffixes:
        label = ms.suffix.lstrip("_")
        type_label = "decimal" if ms.tmdl_type == "decimal" else "whole number"
        suffix_cols = [cc for cc in classified if cc.kind == ms.suffix]
        if suffix_cols:
            lines += ["", f"\t// --- {label} MEASURES ({type_label}) ---"]
            for cc in suffix_cols:
                measure_name = to_title(cc.info.name)
                lines.append(_measure_block(measure_name, table_name, cc.info.name, ms.fmt))
                lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dimension table TMDL
# ---------------------------------------------------------------------------

def _load_strategy_a(dim_def: DimensionDef) -> dict[str, str]:
    """Load visible_columns from dimensions/<alias>.yaml.

    For role-playing dimensions, falls back to dimensions/<inherit>.yaml when the
    alias-specific file doesn't exist and inherit= is set in the dimension config.

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
    # Normalise keys to uppercase
    return {k.upper(): str(v) for k, v in raw.items()}


def build_dimension_tmdl(
    dim_def: DimensionDef,
    columns: list[ColumnInfo],
) -> str:
    """Generate the full TMDL for a dimension table."""
    table_name = to_title(dim_def.alias)   # e.g. "Dates", "Products"

    # Determine visible columns by strategy
    if dim_def.strategy == "A":
        visible_map = _load_strategy_a(dim_def)   # {COL_NAME: display_name}
    else:
        # Strategy B: auto-derive from naming convention
        visible_map = {
            col.name: to_title(col.name)
            for col in columns
            if not is_all_uppercase(col.name)
        }

    lines = [
        f"table '{table_name}'",
        f"\tlineageTag: \"{new_tag()}\"",
        "",
        _m_query(dim_def.schema, dim_def.table, "Table", "import"),
        "",
        "\t// --- PRIMARY KEY (hidden) ---",
        _col_block(dim_def.primary_key, "int64", hidden=True),
        "",
        "\t// --- DIMENSION COLUMNS ---",
    ]

    for col in columns:
        if col.name == dim_def.primary_key:
            continue  # already emitted above
        tmdl_type = sf_type_to_tmdl(col.sf_type, col.numeric_scale)
        if col.name in visible_map:
            display_name = visible_map[col.name]
            lines.append(_col_block(col.name, tmdl_type, hidden=False,
                                    summarize_by="none", display_name=display_name))
        else:
            lines.append(_col_block(col.name, tmdl_type, hidden=True))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# relationships.tmdl
# ---------------------------------------------------------------------------

def build_relationships_tmdl(
    model_def: ModelDef,
    fact_column_names: set[str],
    dim_defs: dict[str, DimensionDef],
) -> str:
    """Generate relationships.tmdl wiring each listed dimension to the fact table.

    Supports per-model fact key overrides via model_def.dim_fact_keys — e.g. when the
    fact table has GAME_PRODUCT_KEY but the Products dimension primary_key is PRODUCT_KEY.

    Only emits a relationship if the resolved fact column actually exists. Skips with a
    warning otherwise.
    """
    import sys
    table_name = model_def.display_name.rsplit(" ", 1)[0]

    lines = []
    for alias in model_def.dimensions:
        dim = dim_defs[alias]
        # Resolve which fact column carries the join key for this dimension
        fact_key = model_def.dim_fact_keys.get(alias, dim.primary_key)

        if fact_key not in fact_column_names:
            print(
                f"  WARNING [{model_def.model_id}]: dimension '{alias}' join key "
                f"'{fact_key}' not found in fact table columns. "
                f"Skipping relationship.",
                file=sys.stderr,
            )
            continue

        dim_table_name = to_title(alias)
        rel_id = new_tag()

        # Dates dimension uses datePartOnly join (DATE_KEY is NUMBER not DATE)
        date_part_line = ""
        if dim.primary_key == "DATE_KEY":
            date_part_line = "\tjoinOnDateBehavior: datePartOnly\n"

        lines.append(
            f"relationship {rel_id}\n"
            f"\tfromTable: '{table_name}'\n"
            f"\tfromColumn: {fact_key}\n"
            f"\ttoTable: '{dim_table_name}'\n"
            f"\ttoColumn: {dim.primary_key}\n"
            f"{date_part_line}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# expressions.tmdl
# ---------------------------------------------------------------------------

def build_expressions_tmdl(sf_config: SnowflakeConfig) -> str:
    """Generate expressions.tmdl with Snowflake connection parameters."""

    def _param(name: str, value: str) -> str:
        return (
            f"expression {name} = \"{value}\" "
            f"meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]\n"
            f"\tlineageTag: \"{new_tag()}\"\n"
        )

    # Build the Snowflake server hostname from account identifier
    server = f"{sf_config.account}.snowflakecomputing.com"

    return "\n".join([
        _param("SnowflakeServer", server),
        _param("SnowflakeWarehouse", sf_config.warehouse),
        _param("SnowflakeRole", sf_config.role),
        _param("SnowflakeDBName", sf_config.database),
    ])


# ---------------------------------------------------------------------------
# model.tmdl
# ---------------------------------------------------------------------------

def build_model_tmdl(model_def: ModelDef, dim_defs: dict[str, DimensionDef]) -> str:
    """Generate model.tmdl."""
    table_name = model_def.display_name.rsplit(" ", 1)[0]
    dim_table_names = [to_title(a) for a in model_def.dimensions]

    ref_lines = "\n".join(f"\tref table '{n}'" for n in dim_table_names)
    ref_lines += f"\n\tref table '{table_name}'"

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
    return "database\n\tcompatibilityLevel: 1605\n"


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
        "version": "4.0",
        "compatibilityLevel": 1605,
    }
    return json.dumps(payload, indent=2)
