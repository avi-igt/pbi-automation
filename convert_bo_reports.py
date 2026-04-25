#!/usr/bin/env python3
"""BO-to-PBI Converter — extract SAP BusinessObjects WebI metadata and generate PBI reports.

Usage:
    python convert_bo_reports.py                        # full pipeline (extract + specs + rdl)
    python convert_bo_reports.py --only extract         # Phase 1: BO API -> JSON
    python convert_bo_reports.py --only specs           # Phase 2: JSON -> .md specs
    python convert_bo_reports.py --only rdl             # Phase 3: .md specs -> .rdl files
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
    print("  SAP BusinessObjects -> Power BI Report Specs")
    print()


def _elapsed(start: float) -> str:
    s = time.time() - start
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60)}s"


def main():
    parser = argparse.ArgumentParser(description="Convert BO WebI reports to PBI specs")
    parser.add_argument(
        "--only",
        choices=["extract", "specs", "rdl"],
        help="Run a single phase (extract=Phase 1, specs=Phase 2, rdl=Phase 3)",
    )
    parser.add_argument("--folder", help="Filter by BO folder (comma-separated, substring, case-insensitive)")
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
    run_rdl = args.only in (None, "rdl")

    json_path = output_dir / "bo-extracted" / "bo_extracted.json"
    specs_dir = output_dir / "bo-specs"

    if run_extract:
        print(f"  Phase 1: Extracting from {config.host}")
        from bo_converter.bo_extractor import extract_all
        json_path = extract_all(
            config,
            output_dir=output_dir,
            folder_filter=args.folder,
            report_filter=args.report,
        )
        print(f"  Phase 1 complete -> {json_path}  ({_elapsed(start)})")
        print()

    if run_specs:
        if not json_path.exists():
            print(f"  ERROR: {json_path} not found -- run --only extract first")
            sys.exit(1)

        print(f"  Phase 2: Generating specs from {json_path}")
        from bo_converter.bo_spec_generator import generate_specs_from_json
        paths = generate_specs_from_json(
            json_path,
            specs_dir,
            report_filter=args.report,
            universe_map=config.universe_map,
        )
        print(f"  Phase 2 complete -> {len(paths)} specs in {specs_dir}  ({_elapsed(start)})")
        print()

    if run_rdl:
        if not specs_dir.exists() or not any(specs_dir.glob("*.md")):
            print(f"  ERROR: no spec files in {specs_dir} -- run --only specs first")
            sys.exit(1)

        rdl_dir = output_dir / "bo-rdl"
        print(f"  Phase 3: Generating RDL from {specs_dir}")
        from report_generator.spec_to_rdl import generate_rdl_from_specs_dir
        results, errors = generate_rdl_from_specs_dir(
            str(specs_dir), str(rdl_dir), args.report or ""
        )
        print(f"  Phase 3 complete -> {len(results)} .rdl files in {rdl_dir}  ({_elapsed(start)})")
        for name, err in errors:
            print(f"  WARNING: {name}: {err}")
        print()

    print(f"  Done in {_elapsed(start)}")


if __name__ == "__main__":
    main()
