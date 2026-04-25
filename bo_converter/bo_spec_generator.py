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


def _slugify(name: str) -> str:
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
        ds_type = _infer_datasource(report)
        model = _infer_semantic_model(report) if ds_type == "semantic_model" else ""

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
        )

        filename = f"{_slugify(name)}.md"
        out_path = output_dir / filename
        out_path.write_text(md, encoding="utf-8")
        log.info("Wrote spec: %s", out_path)
        generated.append(out_path)

    log.info("Generated %d spec files in %s", len(generated), output_dir)
    return generated
