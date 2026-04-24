#!/usr/bin/env python3
"""BO-to-PBI Converter — extract SAP BusinessObjects WebI metadata and generate PBI specs.

Usage:
    python convert_bo_reports.py                        # full pipeline
    python convert_bo_reports.py --only extract         # Phase 1: BO API → JSON
    python convert_bo_reports.py --only specs           # Phase 2: JSON → .md specs
    python convert_bo_reports.py --folder "Sales"       # filter by BO folder
    python convert_bo_reports.py --report "Daily Sales" # filter by report name
"""

import argparse
import logging
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent


def _banner():
    print()
    print("  BO-to-PBI Converter")
    print("  SAP BusinessObjects → Power BI Report Specs")
    print()


def _elapsed(start: float) -> str:
    s = time.time() - start
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60)}s"


def main():
    parser = argparse.ArgumentParser(description="Convert BO WebI reports to PBI specs")
    parser.add_argument(
        "--only",
        choices=["extract", "specs"],
        help="Run a single phase (extract=Phase 1, specs=Phase 2)",
    )
    parser.add_argument("--folder", help="Filter by BO folder (substring, case-insensitive)")
    parser.add_argument("--report", help="Filter by report name (substring, case-insensitive)")
    parser.add_argument("-o", "--output", default="output", help="Base output directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    _banner()
    output_dir = Path(args.output)
    start = time.time()

    from bo_converter.config import BoConfig
    config = BoConfig()

    run_extract = args.only in (None, "extract")
    run_specs = args.only in (None, "specs")

    json_path = output_dir / "bo-extracted" / "bo_extracted.json"

    if run_extract:
        print(f"  Phase 1: Extracting from {config.host}")
        from bo_converter.bo_extractor import extract_all
        json_path = extract_all(
            config,
            output_dir=output_dir,
            folder_filter=args.folder,
            report_filter=args.report,
        )
        print(f"  Phase 1 complete → {json_path}  ({_elapsed(start)})")
        print()

    if run_specs:
        if not json_path.exists():
            print(f"  ERROR: {json_path} not found — run --only extract first")
            sys.exit(1)

        specs_dir = output_dir / "bo-specs"
        print(f"  Phase 2: Generating specs from {json_path}")
        from bo_converter.bo_spec_generator import generate_specs_from_json
        paths = generate_specs_from_json(
            json_path,
            specs_dir,
            report_filter=args.report,
        )
        print(f"  Phase 2 complete → {len(paths)} specs in {specs_dir}  ({_elapsed(start)})")
        print()

    print(f"  Done in {_elapsed(start)}")


if __name__ == "__main__":
    main()
