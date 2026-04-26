"""Phase 2 — convert bo_extracted.json into .md spec files.

Normalises BO JSON into the shape that spec_generator.generate_md() expects,
then delegates rendering. This avoids duplicating any markdown formatting logic.
"""

import json
import logging
import re
from pathlib import Path

from report_generator.spec_generator import generate_md
from report_generator.config import cfg as rpt_cfg

log = logging.getLogger(__name__)


def _md_filename(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _normalise_summary(report: dict) -> dict:
    return {
        "title": report.get("name", ""),
        "legacy_path": report.get("legacy_reports", ""),
        "legacy_users": report.get("legacy_users", ""),
        "description": report.get("summary", ""),
        "format": report.get("report_format", "Paginated"),
        "sort": report.get("sort", "N/A"),
        "folder": report.get("target_folder", ""),
        "notes": report.get("notes", ""),
    }


def _normalise_params(report: dict) -> tuple[list[dict], str]:
    if report.get("filters"):
        return report["filters"], "Filters"
    return report.get("parameters", []), "Parameters"


def _normalise_layout(report: dict) -> list[dict]:
    raw_layout = report.get("layout", {})
    tabs = []
    for section_name, section_data in raw_layout.items():
        columns = section_data.get("columns", [])
        tabs.append({"tab": section_name, "columns": columns})
    return tabs if tabs else [{"tab": "main", "columns": []}]


def _normalise_requirements(report: dict) -> list[str]:
    reqs = report.get("requirements", [])
    return [r.get("text", r) if isinstance(r, dict) else str(r) for r in reqs]


def _extract_universes(report: dict) -> list[str]:
    seen = set()
    result = []
    for dp in report.get("_dataproviders", []):
        name = dp.get("dataSourceName", "")
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _extract_sql(
    report: dict,
    universe_map: dict[str, str] | None = None,
) -> list[dict]:
    result = []
    for dp in report.get("_dataproviders", []):
        sql = dp.get("sql", "")
        if not sql:
            continue
        universe = dp.get("dataSourceName", "")
        ds_type, model = _resolve_universe(universe, universe_map)
        result.append({
            "name": dp.get("name", dp.get("id", "")),
            "universe": universe,
            "sql": sql,
            "custom_sql": dp.get("custom_sql", False),
            "datasource_type": ds_type,
            "model": model,
        })
    return result


_DS_TYPES = {"snowflake", "db2", "semantic_model"}


def _resolve_from_universe_map(
    report: dict, universe_map: dict[str, str] | None
) -> tuple[str, str] | tuple[None, None]:
    if not universe_map:
        return None, None
    for dp in report.get("_dataproviders", []):
        universe = dp.get("dataSourceName", "").lower()
        if universe and universe in universe_map:
            value = universe_map[universe]
            if value.lower() in _DS_TYPES:
                return value.lower(), ""
            return "semantic_model", value
    return None, None


def _resolve_universe(universe: str, universe_map: dict[str, str] | None) -> tuple[str, str]:
    """Resolve a single universe name to (datasource_type, model_name)."""
    if universe_map:
        key = universe.lower()
        if key in universe_map:
            value = universe_map[key]
            if value.lower() in _DS_TYPES:
                return value.lower(), ""
            return "semantic_model", value
    return "", ""


def _infer_datasource(report: dict) -> str:
    ds = report.get("datasource_type", "")
    if ds:
        return ds

    report_for_inference = {
        "name": report.get("name", ""),
        "summary": report.get("summary", ""),
        "notes": report.get("notes", ""),
    }
    return rpt_cfg.infer_datasource(report_for_inference)


def _infer_semantic_model(report: dict) -> str:
    report_for_inference = {
        "name": report.get("name", ""),
        "summary": report.get("summary", ""),
    }
    return rpt_cfg.infer_semantic_model(report_for_inference)


def generate_specs_from_json(
    json_path: Path | str,
    output_dir: Path | str,
    report_filter: str | None = None,
    universe_map: dict[str, str] | None = None,
) -> list[Path]:
    json_path = Path(json_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    reports = data.get("reports", [])

    if report_filter:
        reports = [
            r for r in reports
            if report_filter.lower() in r.get("name", "").lower()
        ]

    generated = []
    for report in reports:
        name = report.get("name", "Untitled")
        summary = _normalise_summary(report)
        params, param_section = _normalise_params(report)
        layout = _normalise_layout(report)
        reqs = _normalise_requirements(report)
        map_ds, map_model = _resolve_from_universe_map(report, universe_map)
        ds_type = map_ds or _infer_datasource(report)
        if ds_type == "semantic_model":
            model = map_model or _infer_semantic_model(report)
        else:
            model = ""
        universes = _extract_universes(report)
        sql_blocks = _extract_sql(report, universe_map)

        md = generate_md(
            report_name=name,
            summary=summary,
            params=params,
            layout=layout,
            reqs=reqs,
            gen_reqs={},
            param_section=param_section,
            datasource_type=ds_type,
            semantic_model=model,
            legacy_universes=universes,
            legacy_sql=sql_blocks,
        )

        filename = f"{_md_filename(name)}.md"
        out_path = output_dir / filename
        out_path.write_text(md, encoding="utf-8")
        log.info("Wrote spec: %s", out_path)
        generated.append(out_path)

    log.info("Generated %d spec files in %s", len(generated), output_dir)
    return generated
