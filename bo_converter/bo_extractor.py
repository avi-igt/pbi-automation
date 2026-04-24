"""Phase 1 orchestrator — enumerate BO documents and write bo_extracted.json."""

import json
import logging
import re
from pathlib import Path

from bo_converter.bo_client import BoClient
from bo_converter.config import BoConfig

log = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name).strip("_")


def extract_all(
    config: BoConfig,
    output_dir: Path | None = None,
    folder_filter: str | None = None,
    report_filter: str | None = None,
) -> Path:
    output_dir = Path(output_dir or "output")
    out_path = output_dir / "bo-extracted"
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "bo_extracted.json"

    reports = []
    errors = []
    total = 0

    with BoClient(config) as client:
        docs = client.enumerate_webi_documents()

        if folder_filter:
            docs = [
                d for d in docs
                if folder_filter.lower() in client.resolve_folder_path(d).lower()
            ]

        if report_filter:
            docs = [
                d for d in docs
                if report_filter.lower() in d.get("name", "").lower()
            ]

        total = len(docs)
        log.info("Extracting %d documents (after filters)", total)

        for i, doc in enumerate(docs, 1):
            doc_id = doc.get("id", "?")
            doc_name = doc.get("name", "?")
            log.info("[%d/%d] %s (id=%s)", i, total, doc_name, doc_id)
            try:
                report = client.extract_report(doc)
                reports.append(report)
            except Exception as e:
                log.warning("Failed to extract %s (id=%s): %s", doc_name, doc_id, e)
                errors.append({
                    "id": str(doc_id),
                    "name": doc_name,
                    "reason": str(e),
                })

    result = {
        "source": config.host,
        "total_reports": total,
        "extracted_count": len(reports),
        "error_count": len(errors),
        "errors": errors,
        "reports": reports,
    }

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s (%d reports, %d errors)", json_path, len(reports), len(errors))

    sql_dir = output_dir / "bo-sql"
    sql_count = _write_sql_files(reports, sql_dir)
    if sql_count:
        log.info("Wrote %d SQL files to %s", sql_count, sql_dir)

    return json_path


def _write_sql_files(reports: list[dict], sql_dir: Path) -> int:
    sql_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for report in reports:
        name = report.get("name", "unknown")
        dps = report.get("_dataproviders", [])
        queries = []
        for dp in dps:
            sql = dp.get("sql", "")
            if not sql:
                continue
            dp_name = dp.get("name", dp.get("id", ""))
            ds_name = dp.get("dataSourceName", "")
            ds_type = dp.get("dataSourceType", "")
            custom = dp.get("custom_sql", False)
            header_lines = [f"-- Data Provider: {dp_name}"]
            if ds_name:
                header_lines.append(f"-- Universe: {ds_name}")
            if ds_type:
                header_lines.append(f"-- Data Source Type: {ds_type}")
            if custom:
                header_lines.append("-- ** Custom/Freehand SQL **")
            header = "\n".join(header_lines)
            queries.append(f"{header}\n\n{sql}")
        if not queries:
            continue
        filename = f"{_slugify(name)}.sql"
        content = f"-- Report: {name}\n-- Extracted from SAP BusinessObjects\n\n" + "\n\n\n".join(queries) + "\n"
        (sql_dir / filename).write_text(content, encoding="utf-8")
        count += 1
    return count
