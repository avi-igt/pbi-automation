"""
clean.py — utility to wipe generated output directories.

Usage:
    python clean.py output                 # wipe all output/ subdirectories
    python clean.py output --rdl           # wipe output/rdl/ only
    python clean.py output --pbip          # wipe output/pbip/ only
    python clean.py output --models        # wipe output/models/ only
    python clean.py output --specs         # wipe output/specs/ only
    python clean.py output --json          # wipe output/json/ only
    python clean.py output --from-spec     # wipe output/from-spec/ only
    python clean.py output --bo-extracted  # wipe output/bo-extracted/ only
    python clean.py output --bo-sql        # wipe output/bo-sql/ only
    python clean.py output --bo-specs      # wipe output/bo-specs/ only
    python clean.py output --bo-rdl        # wipe output/bo-rdl/ only
    python clean.py sql                    # wipe report_generator/sql/ (prompts for confirmation)
    python clean.py sql --yes              # skip confirmation
    python clean.py output sql             # wipe both
    python clean.py --dry-run output       # show what would be deleted without deleting
"""

import argparse
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent

_OUTPUT_SUBDIRS: dict[str, Path] = {
    "rdl":          _REPO_ROOT / "output" / "rdl",
    "pbip":         _REPO_ROOT / "output" / "pbip",
    "specs":        _REPO_ROOT / "output" / "specs",
    "json":         _REPO_ROOT / "output" / "json",
    "models":       _REPO_ROOT / "output" / "models",
    "from-spec":    _REPO_ROOT / "output" / "from-spec",
    "bo-extracted": _REPO_ROOT / "output" / "bo-extracted",
    "bo-sql":       _REPO_ROOT / "output" / "bo-sql",
    "bo-specs":     _REPO_ROOT / "output" / "bo-specs",
    "bo-rdl":       _REPO_ROOT / "output" / "bo-rdl",
}

_SQL_DIR = _REPO_ROOT / "report_generator" / "sql"


def _wipe(path: Path, dry_run: bool) -> int:
    """Delete all contents of a directory, leaving the directory itself.

    Returns the number of items removed (or that would be removed).
    """
    if not path.exists():
        return 0

    items = list(path.iterdir())
    if not items:
        return 0

    if dry_run:
        for item in items:
            print(f"  [dry-run] would delete: {item}")
        return len(items)

    for item in items:
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    return len(items)


def _clean_output(args: argparse.Namespace) -> None:
    """Wipe output/ or selected subdirectories."""
    # Determine which subdirs to clean
    selected = {
        name: path
        for name, path in _OUTPUT_SUBDIRS.items()
        if getattr(args, name.replace("-", "_"), False)
    }
    if not selected:
        selected = _OUTPUT_SUBDIRS   # no flag = all subdirs

    total = 0
    for name, path in selected.items():
        count = _wipe(path, args.dry_run)
        label = "[dry-run] " if args.dry_run else ""
        if count:
            print(f"  {label}output/{name}/  — {count} item(s) removed")
        else:
            print(f"  output/{name}/  — already empty")
        total += count

    if not args.dry_run:
        print(f"\n  Done. {total} item(s) removed.")


def _clean_sql(args: argparse.Namespace) -> None:
    """Wipe report_generator/sql/ — prompts for confirmation unless --yes."""
    if not _SQL_DIR.exists():
        print("  report_generator/sql/  — directory not found, nothing to do.")
        return

    items = list(_SQL_DIR.iterdir())
    if not items:
        print("  report_generator/sql/  — already empty.")
        return

    if args.dry_run:
        for item in items:
            print(f"  [dry-run] would delete: {item.name}")
        print(f"\n  [dry-run] {len(items)} SQL file(s) would be removed.")
        return

    if not args.yes:
        print(
            f"\n  WARNING: report_generator/sql/ contains {len(items)} hand-authored "
            f"SQL file(s).\n  These are not regenerated automatically.\n"
        )
        answer = input("  Type 'yes' to confirm deletion: ").strip().lower()
        if answer != "yes":
            print("  Aborted.")
            return

    count = _wipe(_SQL_DIR, dry_run=False)
    print(f"  report_generator/sql/  — {count} item(s) removed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean generated output directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be deleted without actually deleting.",
    )

    subparsers = parser.add_subparsers(dest="targets", metavar="TARGET")
    subparsers.required = True  # at least one target required

    # ── output subcommand ────────────────────────────────────────────────────
    output_parser = subparsers.add_parser("output", help="Clean output/ directory.")
    output_parser.add_argument("--rdl",          action="store_true", help="Clean output/rdl/")
    output_parser.add_argument("--pbip",         action="store_true", help="Clean output/pbip/")
    output_parser.add_argument("--specs",        action="store_true", help="Clean output/specs/")
    output_parser.add_argument("--json",         action="store_true", help="Clean output/json/")
    output_parser.add_argument("--models",       action="store_true", help="Clean output/models/")
    output_parser.add_argument("--from-spec",    action="store_true", help="Clean output/from-spec/")
    output_parser.add_argument("--bo-extracted", action="store_true", help="Clean output/bo-extracted/")
    output_parser.add_argument("--bo-sql",       action="store_true", help="Clean output/bo-sql/")
    output_parser.add_argument("--bo-specs",     action="store_true", help="Clean output/bo-specs/")
    output_parser.add_argument("--bo-rdl",       action="store_true", help="Clean output/bo-rdl/")

    # ── sql subcommand ───────────────────────────────────────────────────────
    sql_parser = subparsers.add_parser(
        "sql",
        help="Clean report_generator/sql/ (hand-authored files — prompts for confirmation).",
    )
    sql_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt.",
    )

    # argparse only supports one subcommand at a time; handle "output sql" combination
    # by re-parsing if the first positional arg is not a subcommand.
    # Simple approach: detect both words in sys.argv and run both handlers.
    argv = sys.argv[1:]
    run_output = "output" in argv
    run_sql    = "sql"    in argv

    if run_output and run_sql:
        # Parse each block independently
        output_argv = ["output"] + [a for a in argv if a not in ("output", "sql")]
        sql_argv    = ["sql"]    + [a for a in argv if a not in ("output", "sql")]
        output_args = parser.parse_args(output_argv)
        sql_args    = parser.parse_args(sql_argv)
        # Propagate --dry-run
        output_args.dry_run = "--dry-run" in argv
        sql_args.dry_run    = "--dry-run" in argv
        print("\nCleaning output/...")
        _clean_output(output_args)
        print("\nCleaning report_generator/sql/...")
        _clean_sql(sql_args)
    else:
        args = parser.parse_args()
        if args.targets == "output":
            _clean_output(args)
        elif args.targets == "sql":
            _clean_sql(args)


if __name__ == "__main__":
    main()
