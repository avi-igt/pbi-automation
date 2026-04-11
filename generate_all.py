"""
generate_all.py — Run the full FRD → Power BI automation pipeline.

Usage:
    python generate_all.py                         # uses FRD in current dir
    python generate_all.py path/to/FRD.docx        # explicit FRD path
    python generate_all.py path/to/FRD.docx -o ./output  # custom output dir

Steps:
    1. Parse FRD .docx  →  output/json/frd_parsed.json   ← review & edit here
    2. Generate .rdl    →  output/rdl/
    3. Generate .pbip   →  output/pbip/
    4. Generate .md     →  output/specs/  (human-readable review docs)
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows (cp1252 can't encode block-art / star glyphs)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── ANSI colour helpers ────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_O      = "\033[38;5;202m"  # #FF6600 — Brightstar brand orange (primary)
_O2     = "\033[38;5;208m"  # #FF8C00 — Brightstar brand orange (secondary)
_W      = "\033[97m"        # white
_GRAY   = "\033[90m"        # dark gray
# Aliases kept for progress indicators
_Y      = _O    # orange replaces yellow
_B      = _O2   # orange2 replaces blue
_G      = _W    # white replaces green (checkmarks etc.)


def _supports_color() -> bool:
    import os
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.name != "nt"


def _c(code: str, text: str) -> str:
    """Apply ANSI colour only if terminal supports it."""
    if _supports_color():
        return f"{code}{text}{_RESET}"
    return text


# "pbi-automation" full block art — hyphen bar visible on middle rows 2-3
_TOOL_ART = [
    r"  ██████╗ ██████╗ ██╗       █████╗ ██╗   ██╗████████╗ ██████╗ ███╗   ███╗ █████╗ ████████╗██╗  ██████╗ ███╗  ██╗",
    r"  ██╔══██╗██╔══██╗██║      ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗████╗ ████║██╔══██╗╚══██╔══╝██║ ██╔═══██╗████╗ ██║",
    r"  ██████╔╝██████╔╝██║ ─── ███████║██║   ██║   ██║   ██║   ██║██╔████╔██║███████║   ██║   ██║ ██║   ██║██╔██╗██║",
    r"  ██╔═══╝ ██╔══██╗██║ ─── ██╔══██║██║   ██║   ██║   ██║   ██║██║╚██╔╝██║██╔══██║   ██║   ██║ ██║   ██║██║╚████║",
    r"  ██║     ██████╔╝███████╗  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ██║ ╚██████╔╝██║ ╚███║",
    r"  ╚═╝     ╚═════╝ ╚══════╝  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═════╝ ╚═╝  ╚══╝",
]

# Star symbol for Brightstar
_STAR = "★"


def print_banner():
    """Print the colourful CLI banner."""
    # ── Company header ──────────────────────────────────────────────────
    star  = _c(_Y, f" {_STAR} ")
    co    = _c(_BOLD + _Y, "BRIGHTSTAR LOTTERY")
    sep   = _c(_GRAY, "  ·  ")
    tool  = _c(_GRAY, "pbi-automation")
    print()
    print(f"  {star} {co}{sep}{tool}")
    print(_c(_GRAY, "  " + "─" * 72))

    # ── Tool name ASCII art ──────────────────────────────────────────────
    colours = [_Y, _Y, _O, _O, _O, _W]
    for i, line in enumerate(_TOOL_ART):
        c = colours[min(i, len(colours) - 1)]
        print(f"{c}{_BOLD}{line}{_RESET}")

    # ── Tagline strip ───────────────────────────────────────────────────
    print(_c(_GRAY, "  " + "─" * 72))
    flow = (
        _c(_W,    "  FRD")
        + _c(_GRAY, "  →  ")
        + _c(_B,    "frd_parser")
        + _c(_GRAY, "  →  ")
        + _c(_G,    "JSON")
        + _c(_GRAY, "  →  ")
        + _c(_O,    "rdl_generator")
        + _c(_GRAY, " / ")
        + _c(_Y,    "pbip_generator")
    )
    print(flow)
    print(_c(_GRAY, "  github.com/avi-igt/pbi-automation"))
    print(_c(_GRAY, "  " + "─" * 72))
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
from src.spec_generator import generate_all_specs

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
        choices=["parse", "rdl", "pbip", "spec"],
        help="Run only one step: parse=FRD→JSON, rdl=JSON→.rdl, pbip=JSON→.pbip, spec=JSON→.md docs",
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
    # Step 1: Parse FRD → frd_parsed.json  (the human-editable checkpoint)
    # -----------------------------------------------------------------------
    if args.only in (None, "parse", "rdl", "pbip", "spec"):
        _step(1, 4, f"Parsing FRD  ·  {frd_path.name}")
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
        _info("Tip: edit frd_parsed.json before running --only rdl/pbip to customise output")

        if args.only == "parse":
            _done(time.time() - t_start)
            return
    else:
        # Generators called with --only rdl/pbip/spec load the existing JSON
        json_out = output_base / "json" / "frd_parsed.json"
        if not json_out.exists():
            print(f"  {_c(_O, '✖')}  {json_out} not found — run without --only first")
            sys.exit(1)
        with open(json_out) as f:
            frd = json.load(f)

    # Apply --report filter
    if args.report:
        frd = dict(frd)
        frd["reports"] = [r for r in frd["reports"] if args.report.lower() in r["name"].lower()]
        _info(f"Filter: {_c(_W, str(len(frd['reports'])))} reports matching {_c(_Y, repr(args.report))}")

    # -----------------------------------------------------------------------
    # Step 2: Generate .rdl  (Paginated reports)
    # -----------------------------------------------------------------------
    if args.only in (None, "rdl"):
        _step(2, 4, "Generating  .rdl  (Paginated reports)")
        t = time.time()
        rdl_dir = output_base / "rdl"
        rdl_files = generate_all_rdl(frd, str(rdl_dir))
        elapsed = time.time() - t
        _ok(f"{_c(_O, str(len(rdl_files)))} .rdl files  →  {_c(_GRAY, str(rdl_dir))}  {_c(_GRAY, f'({elapsed:.1f}s)')}")
        for f in rdl_files[:4]:
            _info(str(Path(f).relative_to(output_base)))
        if len(rdl_files) > 4:
            _info(f"… and {len(rdl_files) - 4} more")
        if args.only == "rdl":
            _done(time.time() - t_start)
            return

    # -----------------------------------------------------------------------
    # Step 3: Generate .pbip  (Visual reports)
    # -----------------------------------------------------------------------
    if args.only in (None, "pbip"):
        _step(3, 4, "Generating  .pbip  (Visual reports)")
        t = time.time()
        pbip_dir = output_base / "pbip"
        pbip_dirs = generate_all_pbip(frd, str(pbip_dir))
        elapsed = time.time() - t
        _ok(f"{_c(_Y, str(len(pbip_dirs)))} .pbip folders  →  {_c(_GRAY, str(pbip_dir))}  {_c(_GRAY, f'({elapsed:.1f}s)')}")
        for d in pbip_dirs[:4]:
            _info(str(Path(d).relative_to(output_base)))
        if len(pbip_dirs) > 4:
            _info(f"… and {len(pbip_dirs) - 4} more")
        if args.only == "pbip":
            _done(time.time() - t_start)
            return

    # -----------------------------------------------------------------------
    # Step 4: Generate .md spec docs  (human-readable review artifacts)
    # -----------------------------------------------------------------------
    if args.only in (None, "spec"):
        _step(4, 4, "Generating  .md  review docs")
        t = time.time()
        spec_files = generate_all_specs(str(frd_path), str(output_base))
        elapsed = time.time() - t
        if spec_files:
            _ok(f"{_c(_W, str(len(spec_files)))} spec files  →  {_c(_GRAY, str(output_base / 'specs'))}  {_c(_GRAY, f'({elapsed:.1f}s)')}")
            for sf in spec_files[:3]:
                _info(str(Path(sf).name))
            if len(spec_files) > 3:
                _info(f"… and {len(spec_files) - 3} more")
        else:
            _warn("No spec files generated — check FRD path and python-docx installation")

    _done(time.time() - t_start)


def _done(total_elapsed: float):
    print()
    print(_c(_GRAY, f"  {'─' * 60}"))
    print(f"  {_c(_G, '✔')}  {_c(_BOLD + _W, 'Pipeline complete')}  {_c(_GRAY, f'·  {total_elapsed:.1f}s total')}")
    print(_c(_GRAY, "  Review output/ before importing into Power BI / Fabric."))
    print(_c(_GRAY, "  Tip: edit output/json/frd_parsed.json to adjust fields, then re-run."))
    print(_c(_GRAY, f"  {'─' * 60}"))
    print()


if __name__ == "__main__":
    main()
