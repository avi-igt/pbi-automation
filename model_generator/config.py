"""
config.py — reads semantic.properties and exposes typed configuration objects.

Usage:
    from model_generator.config import load_config
    cfg = load_config()                      # reads semantic.properties in repo root
    cfg = load_config(env="d1v1")            # merge [snowflake.d1v1] overrides
    sf  = cfg.snowflake                      # SnowflakeConfig
    dim = cfg.dimensions["dates"]            # DimensionDef
    mdl = cfg.models["financial_daily"]      # ModelDef
"""

import configparser
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_PROPERTIES_FILE = _REPO_ROOT / "semantic.properties"

# Approved display_name postfixes per handbook
_VALID_POSTFIXES = ("LDI", "RSM", "RPT")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MeasureSuffix:
    suffix: str     # e.g. "_COUNT" — must end column names to trigger measure creation
    tmdl_type: str  # "int64" | "decimal"
    fmt: str        # Power BI format string, e.g. "0" or "#,##0.00"


_DEFAULT_MEASURE_SUFFIXES = [
    MeasureSuffix("_COUNT",    "int64",   "0"),
    MeasureSuffix("_AMOUNT",   "decimal", "#,##0.00"),
    MeasureSuffix("_QUANTITY", "int64",   "#,##0"),
]


@dataclass
class SnowflakeConfig:
    account: str
    warehouse: str
    database: str
    role: str
    authenticator: str = "snowflake"   # "snowflake" (user/pass) or "externalbrowser" (SSO)


@dataclass
class DimensionDef:
    alias: str          # config key, e.g. "dates"
    source: str         # full SCHEMA.TABLE, e.g. "DIMCORE.DATES"
    schema: str         # e.g. "DIMCORE"
    table: str          # e.g. "DATES"
    primary_key: str    # e.g. "DATE_KEY"
    strategy: str       # "A" or "B"
    inherit: str = ""   # alias to inherit Strategy A YAML from (role-playing dims)


@dataclass
class ModelDef:
    model_id: str               # config key, e.g. "financial_daily"
    display_name: str           # e.g. "Financial Daily LDI"
    fact_schema: str            # e.g. "FINANCIAL"
    fact_table: str             # e.g. "FINANCIAL_DAILY"
    dimensions: list[str]       # aliases in order, e.g. ["dates", "products", "locations"]
    dim_fact_keys: dict[str, str] = None  # alias → fact column override, e.g. {"products": "GAME_PRODUCT_KEY"}
                                          # if absent for an alias, falls back to dim's primary_key

    def __post_init__(self):
        if self.dim_fact_keys is None:
            self.dim_fact_keys = {}


@dataclass
class SemanticConfig:
    snowflake: SnowflakeConfig
    dimensions: dict[str, DimensionDef]
    models: dict[str, ModelDef]
    measure_suffixes: list[MeasureSuffix]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_dimension_value(alias: str, raw: str) -> DimensionDef:
    """Parse a [dimensions] entry value.

    Format: SCHEMA.TABLE, primary_key=KEY_COL, strategy=A
    """
    parts = [p.strip() for p in raw.split(",")]
    source = parts[0]
    if "." not in source:
        raise ValueError(
            f"[dimensions] {alias}: source must be SCHEMA.TABLE, got '{source}'"
        )
    schema, table = source.split(".", 1)

    kwargs: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            kwargs[k.strip().lower()] = v.strip()

    primary_key = kwargs.get("primary_key", "")
    if not primary_key:
        raise ValueError(
            f"[dimensions] {alias}: missing primary_key= in '{raw}'"
        )

    strategy = kwargs.get("strategy", "A").upper()
    if strategy not in ("A", "B"):
        raise ValueError(
            f"[dimensions] {alias}: strategy must be A or B, got '{strategy}'"
        )

    inherit = kwargs.get("inherit", "").strip()

    return DimensionDef(
        alias=alias,
        source=source,
        schema=schema.upper(),
        table=table.upper(),
        primary_key=primary_key.upper(),
        strategy=strategy,
        inherit=inherit,
    )


def _parse_model_section(model_id: str, cp: configparser.ConfigParser,
                          section: str) -> ModelDef:
    """Parse a [model.*] section."""

    def _req(key: str) -> str:
        try:
            return cp.get(section, key).strip()
        except configparser.NoOptionError:
            raise ValueError(f"[{section}]: missing required key '{key}'")

    display_name = _req("display_name")
    fact_table_raw = _req("fact_table").upper()
    dimensions_raw = _req("dimensions")

    if "." not in fact_table_raw:
        raise ValueError(
            f"[{section}] fact_table must be SCHEMA.TABLE, got '{fact_table_raw}'"
        )
    fact_schema, fact_table = fact_table_raw.split(".", 1)

    # Parse dimension aliases with optional fact key override: "products:GAME_PRODUCT_KEY"
    dimensions = []
    dim_fact_keys: dict[str, str] = {}
    for raw in dimensions_raw.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if ":" in raw:
            alias, fact_key = raw.split(":", 1)
            alias = alias.strip()
            fact_key = fact_key.strip().upper()
            dimensions.append(alias)
            dim_fact_keys[alias] = fact_key
        else:
            dimensions.append(raw)

    return ModelDef(
        model_id=model_id,
        display_name=display_name,
        fact_schema=fact_schema,
        fact_table=fact_table,
        dimensions=dimensions,
        dim_fact_keys=dim_fact_keys,
    )


def _validate_display_name(model_id: str, display_name: str) -> None:
    """Warn if display_name does not end with an approved handbook postfix."""
    if not any(display_name.strip().endswith(p) for p in _VALID_POSTFIXES):
        print(
            f"  WARNING [{model_id}] display_name '{display_name}' does not end "
            f"with a required postfix ({', '.join(_VALID_POSTFIXES)}). "
            f"Update per handbook Section 1.1.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_config(
    properties_file: Path | None = None,
    env: str | None = None,
) -> SemanticConfig:
    """Read semantic.properties and return a SemanticConfig.

    Args:
        properties_file: path to the .properties file (default: repo root).
        env: environment name (e.g. 'd1v1'). When given, values in
             [snowflake.<env>] override the base [snowflake] section.
    """
    path = properties_file or _PROPERTIES_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Expected at: {_PROPERTIES_FILE}"
        )

    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"))
    cp.optionxform = str   # preserve case
    cp.read(path, encoding="utf-8")

    # ── Snowflake config ────────────────────────────────────────────────────
    def _sf_get(key: str, default: str = "") -> str:
        # Try env-specific section first, fall back to base [snowflake]
        if env:
            env_section = f"snowflake.{env}"
            try:
                return cp.get(env_section, key).strip()
            except (configparser.NoSectionError, configparser.NoOptionError):
                pass
        try:
            return cp.get("snowflake", key).strip()
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    sf_config = SnowflakeConfig(
        account=_sf_get("account"),
        warehouse=_sf_get("warehouse"),
        database=_sf_get("database"),
        role=_sf_get("role"),
        authenticator=_sf_get("authenticator", "snowflake"),
    )
    if not sf_config.account:
        raise ValueError("[snowflake] account is required in semantic.properties")

    # ── Dimensions ──────────────────────────────────────────────────────────
    dimensions: dict[str, DimensionDef] = {}
    if cp.has_section("dimensions"):
        for alias, raw in cp.items("dimensions"):
            dimensions[alias] = _parse_dimension_value(alias, raw)

    # ── Models ──────────────────────────────────────────────────────────────
    models: dict[str, ModelDef] = {}
    for section in cp.sections():
        if not section.startswith("model."):
            continue
        model_id = section[len("model."):]
        model_def = _parse_model_section(model_id, cp, section)
        _validate_display_name(model_id, model_def.display_name)

        # Validate dimension aliases are declared
        for alias in model_def.dimensions:
            if alias not in dimensions:
                raise ValueError(
                    f"[{section}] references unknown dimension '{alias}'. "
                    f"Declare it in [dimensions] first."
                )
        models[model_id] = model_def

    if not models:
        raise ValueError(
            "No [model.*] sections found in semantic.properties. "
            "Add at least one [model.<id>] section."
        )

    # ── Measure suffixes ────────────────────────────────────────────────────
    measure_suffixes: list[MeasureSuffix] = []
    if cp.has_section("measure_suffixes"):
        for suffix, raw in cp.items("measure_suffixes"):
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) < 2:
                raise ValueError(
                    f"[measure_suffixes] {suffix}: expected 'tmdl_type, format_string', "
                    f"got '{raw}'"
                )
            measure_suffixes.append(MeasureSuffix(
                suffix=suffix.upper(),
                tmdl_type=parts[0],
                fmt=parts[1],
            ))

    if not measure_suffixes:
        measure_suffixes = list(_DEFAULT_MEASURE_SUFFIXES)

    return SemanticConfig(
        snowflake=sf_config,
        dimensions=dimensions,
        models=models,
        measure_suffixes=measure_suffixes,
    )
