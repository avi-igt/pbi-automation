"""Phase 1 orchestrator — enumerate BO documents and write bo_extracted.json."""

import json
import logging
from pathlib import Path

from bo_converter.bo_client import BoClient
from bo_converter.config import BoConfig

log = logging.getLogger(__name__)


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
                if folder_filter.lower() in d.get("SI_PATH", "").lower()
            ]

        if report_filter:
            docs = [
                d for d in docs
                if report_filter.lower() in d.get("SI_NAME", "").lower()
            ]

        total = len(docs)
        log.info("Extracting %d documents (after filters)", total)

        for i, doc in enumerate(docs, 1):
            doc_id = doc.get("SI_ID", "?")
            doc_name = doc.get("SI_NAME", "?")
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

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log.info("Wrote %s (%d reports, %d errors)", json_path, len(reports), len(errors))
    return json_path
