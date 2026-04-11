"""
spec_to_pbip.py — Generate .pbip visual reports from reviewed spec .md files.

This is the second-path generator: instead of FRD.docx → JSON → .pbip,
it reads a spec .md (which a developer has reviewed and may have confirmed
the semantic model, page layout, slicer fields, etc.) and produces the
.pbip folder structure directly.

Usage:
    # Single spec file
    python src/spec_to_pbip.py output/specs/cash-pop-performance.md

    # All Visual specs in a directory
    python src/spec_to_pbip.py output/specs/

    # Custom output directory
    python src/spec_to_pbip.py output/specs/ -o output/from-spec/pbip

    # Filter by report name
    python src/spec_to_pbip.py output/specs/ --report "Cash Pop"

Library usage:
    from src.spec_to_pbip import generate_pbip_from_spec
    out_path = generate_pbip_from_spec("output/specs/cash-pop-performance.md", "output/from-spec/pbip")
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.spec_parser import parse_spec
from src.pbip_generator import generate_pbip


def generate_pbip_from_spec(md_path: str, output_dir: str) -> str:
    """
    Parse a spec .md and write the corresponding .pbip folder structure.

    Parameters
    ----------
    md_path : str
        Path to the spec .md file.
    output_dir : str
        Root output directory.  The .Report folder is written under a sub-
        folder named after the report's Output Folder (same layout as the
        main pipeline).

    Returns
    -------
    str
        Absolute path of the generated .Report folder.

    Raises
    ------
    ValueError
        If the spec describes a Paginated report — use spec_to_rdl.py instead.
    """
    report = parse_spec(md_path)

    if report["report_format"] != "Visual":
        raise ValueError(
            f"{Path(md_path).name}: report_format is '{report['report_format']}'"
            " — use spec_to_rdl.py for Paginated reports"
        )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return generate_pbip(report, output_dir)


def generate_pbip_from_specs_dir(
    specs_dir: str,
    output_dir: str,
    report_filter: str = "",
) -> tuple[list, list]:
    """
    Generate .pbip folders from all Visual spec .md files in *specs_dir*.

    Returns (generated_paths, error_list) where error_list contains
    (filename, error_message) tuples.
    """
    specs = sorted(Path(specs_dir).glob("*.md"))
    results = []
    errors = []

    for md in specs:
        if report_filter and report_filter.lower() not in md.stem.replace("-", " ").lower():
            continue
        try:
            report = parse_spec(str(md))
            if report["report_format"] != "Visual":
                continue          # skip Paginated specs silently
            out = generate_pbip_from_spec(str(md), output_dir)
            results.append(out)
        except Exception as exc:
            errors.append((md.name, str(exc)))

    return results, errors


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Generate .pbip visual reports from reviewed spec .md files"
    )
    ap.add_argument(
        "spec",
        help="Path to a spec .md file OR a directory containing spec .md files",
    )
    ap.add_argument(
        "-o", "--output",
        default="output/from-spec/pbip",
        help="Output directory (default: output/from-spec/pbip)",
    )
    ap.add_argument(
        "--report",
        default="",
        metavar="NAME",
        help="Only process specs whose filename contains NAME (partial, case-insensitive)",
    )
    args = ap.parse_args()

    spec_path = Path(args.spec)

    if spec_path.is_file():
        try:
            out = generate_pbip_from_spec(str(spec_path), args.output)
            print(f"  ✔  {spec_path.name}  →  {out}")
        except Exception as exc:
            print(f"  ✖  {spec_path.name}: {exc}", file=sys.stderr)
            sys.exit(1)

    elif spec_path.is_dir():
        results, errors = generate_pbip_from_specs_dir(
            str(spec_path), args.output, args.report
        )
        print(f"Generated {len(results)} .pbip folders  →  {args.output}")
        for f in results[:10]:
            print(f"  {Path(f).name}")
        if len(results) > 10:
            print(f"  … and {len(results) - 10} more")
        for name, err in errors:
            print(f"  ⚠  {name}: {err}", file=sys.stderr)
        if errors:
            sys.exit(1)

    else:
        print(f"  ✖  Not found: {spec_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
