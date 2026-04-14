"""
spec_to_rdl.py — Generate .rdl paginated reports from reviewed spec .md files.

This is the second-path generator: instead of FRD.docx → JSON → .rdl,
it reads a spec .md (which a developer has reviewed and may have filled in
the SQL, confirmed the table name, etc.) and produces the .rdl directly.

Usage:
    # Single spec file
    python src/spec_to_rdl.py output/specs/mo-wild-ball-sales-report.md

    # All Paginated specs in a directory
    python src/spec_to_rdl.py output/specs/

    # Custom output directory
    python src/spec_to_rdl.py output/specs/ -o output/from-spec/rdl

    # Filter by report name
    python src/spec_to_rdl.py output/specs/ --report "1042 Tax"

Library usage:
    from report_generator.spec_to_rdl import generate_rdl_from_spec
    out_path = generate_rdl_from_spec("output/specs/1042-tax.md", "output/from-spec/rdl")
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from report_generator.spec_parser import parse_spec
from report_generator.rdl_generator import generate_rdl


def generate_rdl_from_spec(md_path: str, output_dir: str) -> str:
    """
    Parse a spec .md and write the corresponding .rdl file.

    Parameters
    ----------
    md_path : str
        Path to the spec .md file.
    output_dir : str
        Root output directory.  The .rdl is written under a sub-folder named
        after the report's Output Folder (same layout as the main pipeline).

    Returns
    -------
    str
        Absolute path of the generated .rdl file.

    Raises
    ------
    ValueError
        If the spec describes a Visual report — use spec_to_pbip.py instead.
    """
    report = parse_spec(md_path)

    if report["report_format"] != "Paginated":
        raise ValueError(
            f"{Path(md_path).name}: report_format is '{report['report_format']}'"
            " — use spec_to_pbip.py for Visual reports"
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    folder = re.sub(r"\W+", "_", report.get("target_folder") or report.get("folder", "Output"))
    subfolder = out / folder
    subfolder.mkdir(exist_ok=True)

    safe = re.sub(r"[^\w\s\-]", "", report["name"]).strip().replace(" ", "_")
    out_file = subfolder / f"{safe}.rdl"
    out_file.write_text(generate_rdl(report), encoding="utf-8")
    return str(out_file)


def generate_rdl_from_specs_dir(
    specs_dir: str,
    output_dir: str,
    report_filter: str = "",
) -> tuple[list, list]:
    """
    Generate .rdl files from all Paginated spec .md files in *specs_dir*.

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
            if report["report_format"] != "Paginated":
                continue          # skip Visual specs silently
            out = generate_rdl_from_spec(str(md), output_dir)
            results.append(out)
        except Exception as exc:
            errors.append((md.name, str(exc)))

    return results, errors


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Generate .rdl paginated reports from reviewed spec .md files"
    )
    ap.add_argument(
        "spec",
        help="Path to a spec .md file OR a directory containing spec .md files",
    )
    ap.add_argument(
        "-o", "--output",
        default="output/from-spec/rdl",
        help="Output directory (default: output/from-spec/rdl)",
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
            out = generate_rdl_from_spec(str(spec_path), args.output)
            print(f"  ✔  {spec_path.name}  →  {out}")
        except Exception as exc:
            print(f"  ✖  {spec_path.name}: {exc}", file=sys.stderr)
            sys.exit(1)

    elif spec_path.is_dir():
        results, errors = generate_rdl_from_specs_dir(
            str(spec_path), args.output, args.report
        )
        print(f"Generated {len(results)} .rdl files  →  {args.output}")
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
