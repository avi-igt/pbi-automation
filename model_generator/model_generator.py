"""
model_generator.py — orchestrates generation of one complete .SemanticModel folder
and its companion .Report placeholder folder.

Usage:
    from model_generator.model_generator import ModelGenerator

    gen = ModelGenerator(config, snowflake_client)
    gen.generate(model_def, output_dir=Path("output"))
"""

import shutil
import sys
from pathlib import Path

from model_generator.config import SemanticConfig, ModelDef
from model_generator.snowflake_client import SnowflakeClient
from model_generator.tmdl_builder import (
    DimMergeSpec,
    build_database_tmdl,
    build_definition_pbism,
    build_dim_merge_spec,
    build_dimension_tmdl,
    build_expressions_tmdl,
    build_fact_table_tmdl,
    build_model_tmdl,
    build_platform_json,
    build_relationships_tmdl,
    to_title,
)
from model_generator.report_builder import (
    build_definition_pbir,
    build_local_settings_json,
    build_page_json,
    build_pages_json,
    build_pbip_file,
    build_placeholder_visual,
    build_report_json,
    build_report_platform_json,
    build_version_json,
    new_report_ids,
)

_THEME_TEMPLATE = Path(__file__).parent / "templates" / "BaseThemes" / "CY24SU10.json"
_THEME_NAME = "CY24SU10"


class ModelGenerator:
    def __init__(self, config: SemanticConfig, sf_client: SnowflakeClient):
        self._cfg = config
        self._sf = sf_client

    def generate(self, model_def: ModelDef, output_dir: Path) -> Path:
        """Generate the complete .SemanticModel and companion .Report folders.

        Returns the path to the generated .SemanticModel folder.
        """
        folder_name = f"{model_def.display_name}.SemanticModel"
        model_dir = output_dir / folder_name

        # Full regeneration — wipe any previous output
        if model_dir.exists():
            shutil.rmtree(model_dir)

        tables_dir = model_dir / "definition" / "tables"
        tables_dir.mkdir(parents=True)

        print(f"\n  Generating: {model_def.display_name}", file=sys.stderr)

        # ── 1. Fetch fact table metadata ────────────────────────────────────
        print(f"    Fetching columns: {model_def.fact_schema}.{model_def.fact_table}",
              file=sys.stderr)
        fact_columns = self._sf.get_columns(model_def.fact_schema, model_def.fact_table)
        fact_obj_kind = self._sf.get_object_type(model_def.fact_schema, model_def.fact_table)
        fact_col_names = {c.name for c in fact_columns}
        print(f"    {len(fact_columns)} columns found ({fact_obj_kind})", file=sys.stderr)

        # ── 2. Fetch dimension metadata ─────────────────────────────────────
        dim_columns: dict[str, list] = {}
        for alias in model_def.dimensions:
            dim_def = self._cfg.dimensions[alias]
            strategy_label = f"Strategy {dim_def.strategy}"
            print(f"    Fetching columns ({strategy_label}): {dim_def.source}",
                  file=sys.stderr)
            dim_columns[alias] = self._sf.get_columns(dim_def.schema, dim_def.table)
            print(f"    {len(dim_columns[alias])} columns found", file=sys.stderr)

        # Build dim merge specs — describe how each dimension joins + which cols to expand
        dim_specs: list[DimMergeSpec] = [
            build_dim_merge_spec(
                self._cfg.dimensions[alias],
                dim_columns[alias],
                model_def.dim_fact_keys.get(alias, self._cfg.dimensions[alias].primary_key),
            )
            for alias in model_def.dimensions
        ]

        # ── 3. Build TMDL content strings ───────────────────────────────────
        fact_tmdl = build_fact_table_tmdl(
            model_def, fact_columns, fact_obj_kind,
            self._cfg.measure_suffixes, dim_specs, model_def.filter_column,
        )
        dim_tmdls = {
            alias: build_dimension_tmdl(
                self._cfg.dimensions[alias], dim_columns[alias]
            )
            for alias in model_def.dimensions
        }
        relationships_tmdl = build_relationships_tmdl(
            model_def, fact_col_names, self._cfg.dimensions
        )
        expressions_tmdl = build_expressions_tmdl(
            self._cfg.snowflake,
            has_date_filter=bool(model_def.filter_column),
        )
        model_tmdl = build_model_tmdl(model_def, self._cfg.dimensions)
        database_tmdl = build_database_tmdl()
        platform_json = build_platform_json(model_def)
        definition_pbism = build_definition_pbism()

        # ── 4. Write SemanticModel files ────────────────────────────────────
        _write(model_dir / ".platform", platform_json)
        _write(model_dir / "definition.pbism", definition_pbism)
        _write(model_dir / "definition" / "database.tmdl", database_tmdl)
        _write(model_dir / "definition" / "model.tmdl", model_tmdl)
        _write(model_dir / "definition" / "expressions.tmdl", expressions_tmdl)
        if relationships_tmdl:
            _write(model_dir / "definition" / "relationships.tmdl", relationships_tmdl)

        # Fact table file — name matches display_name minus postfix
        table_name = model_def.display_name.rsplit(" ", 1)[0]
        _write(tables_dir / f"{table_name}.tmdl", fact_tmdl)

        # Dimension table files
        for alias, tmdl_content in dim_tmdls.items():
            dim_table_name = to_title(alias)
            _write(tables_dir / f"{dim_table_name}.tmdl", tmdl_content)

        _report_summary(model_def, fact_columns, model_dir, self._cfg.measure_suffixes)

        # ── 5. Generate companion .Report placeholder ───────────────────────
        self._generate_report(model_def, output_dir)

        return model_dir

    def _generate_report(self, model_def: ModelDef, output_dir: Path) -> Path:
        """Generate the companion .Report placeholder folder."""
        report_dir = output_dir / f"{model_def.display_name}.Report"

        if report_dir.exists():
            shutil.rmtree(report_dir)

        page_id, visual_id = new_report_ids()

        # ── Directory structure ─────────────────────────────────────────────
        pages_dir = report_dir / "definition" / "pages" / page_id
        visuals_dir = pages_dir / "visuals" / visual_id
        pbi_dir = report_dir / ".pbi"
        theme_dir = (
            report_dir / "definition" / "StaticResources"
            / "SharedResources" / "BaseThemes"
        )

        for d in (pages_dir, visuals_dir, pbi_dir, theme_dir):
            d.mkdir(parents=True)

        # ── Files ───────────────────────────────────────────────────────────
        _write(report_dir / ".platform",         build_report_platform_json(model_def))
        _write(report_dir / "definition.pbir",   build_definition_pbir(model_def))
        _write(pbi_dir / "localSettings.json",   build_local_settings_json())

        _write(report_dir / "definition" / "report.json",  build_report_json())
        _write(report_dir / "definition" / "version.json", build_version_json())
        _write(
            report_dir / "definition" / "pages" / "pages.json",
            build_pages_json(page_id),
        )
        _write(pages_dir / "page.json",             build_page_json(page_id, model_def))
        _write(visuals_dir / "visual.json",          build_placeholder_visual(visual_id, model_def))

        # ── Theme file ──────────────────────────────────────────────────────
        if _THEME_TEMPLATE.exists():
            shutil.copy2(_THEME_TEMPLATE, theme_dir / f"{_THEME_NAME}.json")
        else:
            print(
                f"  WARNING: Theme template not found at {_THEME_TEMPLATE}. "
                f"Copy CY24SU10.json to model_generator/templates/BaseThemes/ manually.",
                file=sys.stderr,
            )

        # ── .pbip project file (sits alongside .Report and .SemanticModel) ──
        pbip_path = output_dir / f"{model_def.display_name}.pbip"
        _write(pbip_path, build_pbip_file(model_def))

        print(f"    Report:     {report_dir.name}", file=sys.stderr)
        print(f"    PBIP:       {pbip_path.name}", file=sys.stderr)
        return report_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _report_summary(
    model_def: ModelDef,
    fact_columns: list,
    model_dir: Path,
    measure_suffixes: list,
) -> None:
    counts = {
        ms.suffix: sum(1 for c in fact_columns if c.name.endswith(ms.suffix))
        for ms in measure_suffixes
    }
    total = sum(counts.values())
    breakdown = " + ".join(
        f"{v} {ms.suffix.lstrip('_').lower()}"
        for ms, v in zip(measure_suffixes, counts.values())
        if v
    )
    print(
        f"    Done: {total} measures ({breakdown})  →  {model_dir.name}",
        file=sys.stderr,
    )
