"""
generate_all.py — Run the full FRD → Power BI automation pipeline.

Usage:
    python generate_all.py                         # uses FRD in current dir
    python generate_all.py path/to/FRD.docx        # explicit FRD path
    python generate_all.py path/to/FRD.docx -o ./output  # custom output dir

Steps:
    1. Parse FRD .docx → output/json/frd_parsed.json
    2. Generate .rdl files for all Paginated reports → output/rdl/
    3. Generate .pbip folders for all Visual reports → output/pbip/
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── ANSI colour helpers ────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_Y      = "\033[93m"   # yellow  (Power BI brand)
_O      = "\033[38;5;208m"  # orange
_B      = "\033[94m"   # blue
_G      = "\033[92m"   # green
_P      = "\033[95m"   # purple
_W      = "\033[97m"   # white
_GRAY   = "\033[90m"   # dark gray


def _supports_color() -> bool:
    import os
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.name != "nt"


def _c(code: str, text: str) -> str:
    """Apply ANSI colour only if terminal supports it."""
    if _supports_color():
        return f"{code}{text}{_RESET}"
    return text


BANNER = r"""
  ██████  ██████  ██       █████  ██    ██ ████████  ██████  ███    ███  █████  ████████ ██  ██████  ███    ██
  ██   ██ ██   ██ ██      ██   ██ ██    ██    ██    ██    ██ ████  ████ ██   ██    ██    ██ ██    ██ ████   ██
  ██████  ██████  ██      ███████ ██    ██    ██    ██    ██ ██ ████ ██ ███████    ██    ██ ██    ██ ██ ██  ██
  ██      ██   ██ ██      ██   ██ ██    ██    ██    ██    ██ ██  ██  ██ ██   ██    ██    ██ ██    ██ ██  ██ ██
  ██      ██████  ███████ ██   ██  ██████     ██     ██████  ██      ██ ██   ██    ██    ██  ██████  ██   ████
"""

BANNER_COMPACT = """
  ██████╗ ██████╗ ██╗      █████╗ ██╗   ██╗████████╗ ██████╗
  ██╔══██╗██╔══██╗██║     ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗
  ██████╔╝██████╔╝██║     ███████║██║   ██║   ██║   ██║   ██║
  ██╔═══╝ ██╔══██╗██║     ██╔══██║██║   ██║   ██║   ██║   ██║
  ██║     ██████╔╝███████╗██║  ██║╚██████╔╝   ██║   ╚██████╔╝
  ╚═╝     ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝
"""


def print_banner():
    """Print the colourful CLI banner."""
    if _supports_color():
        lines = BANNER_COMPACT.split("\n")
        colours = [_Y, _Y, _O, _O, _O, _W]
        for i, line in enumerate(lines):
            c = colours[min(i, len(colours) - 1)]
            print(f"{c}{_BOLD}{line}{_RESET}")
    else:
        print(BANNER_COMPACT)

    tagline   = _c(_GRAY, "  ─────────────────────────────────────────────────────────────────────")
    subtitle  = _c(_W, "  FRD") + _c(_GRAY, "  →  ") + _c(_B, "Parser") + _c(_GRAY, "  →  ") + _c(_G, "JSON") + _c(_GRAY, "  →  ") + _c(_O, ".rdl") + _c(_GRAY, " / ") + _c(_Y, ".pbip")
    credit    = _c(_GRAY, "  Power BI Report Automation  ·  github.com/avi-igt/pbi-automation")
    print(tagline)
    print(subtitle)
    print(credit)
    print(tagline)
    print()


def _step(n: int, total: int, label: str):
    bar   = _c(_Y, "●")
    rest  = _c(_GRAY, "○")
    dots  = " ".join([bar if i < n else rest for i in range(total)])
    print(f"\n  {dots}  {_c(_BOLD + _W, label)}")
    print(_c(_GRAY, f"  {'─' * 60}"))


def _ok(msg: str):
    print(f"  {_c(_G, '✔')}  {msg}")


def _info(msg: str):
    print(f"  {_c(_B, '·')}  {_c(_GRAY, msg)}")


def _warn(msg: str):
    print(f"  {_c(_Y, '⚠')}  {msg}")

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent))

from src.frd_parser import parse_frd
from src.rdl_generator import generate_all_rdl
from src.pbip_generator import generate_all_pbip

# Default FRD file — place the .docx in the same directory as this script
DEFAULT_FRD = Path(__file__).parent / "MO - Performance Wizard Ad Hoc Reporting FRD v1.0.docx"


def main():
    print_banner()
    ap = argparse.ArgumentParser(description="Generate Power BI report files from FRD")
    ap.add_argument(
        "frd",
        nargs="?",
        default=str(DEFAULT_FRD),
        help="Path to the FRD .docx file (default: local copy in repo root)",
    )
    ap.add_argument(
        "-o", "--output",
        default=str(Path(__file__).parent / "output"),
        help="Output base directory (default: ./output)",
    )
    ap.add_argument(
        "--only",
        choices=["parse", "rdl", "pbip"],
        help="Run only one step instead of the full pipeline",
    )
    ap.add_argument(
        "--report",
        help="Filter: only generate files for reports whose name contains this string",
    )
    args = ap.parse_args()

    frd_path = Path(args.frd)
    output_base = Path(args.output)

    if not frd_path.exists():
        print(f"  {_c(_O, '✖')}  FRD not found: {_c(_W, str(frd_path))}")
        _info("Place the .docx in the repo root or pass the path as an argument.")
        sys.exit(1)

    t_start = time.time()

    # -----------------------------------------------------------------------
    # Step 1: Parse FRD
    # -----------------------------------------------------------------------
    if args.only in (None, "parse", "rdl", "pbip"):
        _step(1, 3, f"Parsing FRD  ·  {frd_path.name}")
        t = time.time()
        frd = parse_frd(str(frd_path))
        elapsed = time.time() - t

        json_out = output_base / "json" / "frd_parsed.json"
        json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(json_out, "w") as f:
            json.dump(frd, f, indent=2)

        _ok(f"{_c(_W, str(frd['total_reports']))} reports parsed  {_c(_GRAY, f'({elapsed:.1f}s)')}")
        _info(f"{_c(_O, str(frd['paginated_count']))} paginated (.rdl)   {_c(_Y, str(frd['visual_count']))} visual (.pbip)")
        if frd.get("unknown_count"):
            _warn(f"{frd['unknown_count']} unknown format — check report_format in JSON")
        _ok(f"JSON  →  {_c(_GRAY, str(json_out))}")
    else:
        json_out = output_base / "json" / "frd_parsed.json"
        if not json_out.exists():
            print(f"  {_c(_O, '✖')}  Run without --only first to generate {json_out}")
            sys.exit(1)
        with open(json_out) as f:
            frd = json.load(f)

    # Apply report filter
    if args.report:
        frd_filtered = dict(frd)
        frd_filtered["reports"] = [
            r for r in frd["reports"]
            if args.report.lower() in r["name"].lower()
        ]
        _info(f"Filter: {_c(_W, str(len(frd_filtered['reports'])))} reports matching {_c(_Y, repr(args.report))}")
    else:
        frd_filtered = frd

    # -----------------------------------------------------------------------
    # Step 2: Generate RDL (Paginated reports)
    # -----------------------------------------------------------------------
    if args.only in (None, "rdl"):
        _step(2, 3, "Generating  .rdl  (Paginated reports)")
        t = time.time()
        rdl_dir = output_base / "rdl"
        rdl_files = generate_all_rdl(frd_filtered, str(rdl_dir))
        elapsed = time.time() - t
        _ok(f"{_c(_O, str(len(rdl_files)))} .rdl files  →  {_c(_GRAY, str(rdl_dir))}  {_c(_GRAY, f'({elapsed:.1f}s)')}")
        for f in rdl_files[:4]:
            _info(str(Path(f).relative_to(output_base)))
        if len(rdl_files) > 4:
            _info(f"… and {len(rdl_files) - 4} more")

    # -----------------------------------------------------------------------
    # Step 3: Generate PBIP (Visual reports)
    # -----------------------------------------------------------------------
    if args.only in (None, "pbip"):
        _step(3, 3, "Generating  .pbip  (Visual reports)")
        t = time.time()
        pbip_dir = output_base / "pbip"
        pbip_dirs = generate_all_pbip(frd_filtered, str(pbip_dir))
        elapsed = time.time() - t
        _ok(f"{_c(_Y, str(len(pbip_dirs)))} .pbip report folders  →  {_c(_GRAY, str(pbip_dir))}  {_c(_GRAY, f'({elapsed:.1f}s)')}")
        for d in pbip_dirs[:4]:
            _info(str(Path(d).relative_to(output_base)))
        if len(pbip_dirs) > 4:
            _info(f"… and {len(pbip_dirs) - 4} more")

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    total_elapsed = time.time() - t_start
    print()
    print(_c(_GRAY, f"  {'─' * 60}"))
    print(f"  {_c(_G, '✔')}  {_c(_BOLD + _W, 'Pipeline complete')}  {_c(_GRAY, f'·  {total_elapsed:.1f}s total')}")
    print(_c(_GRAY, "  Review output/ files before importing into Power BI / Fabric."))
    print(_c(_GRAY, "  Each .pbip folder has a README.md with a developer TODO checklist."))
    print(_c(_GRAY, f"  {'─' * 60}"))
    print()


if __name__ == "__main__":
    main()
