#!/usr/bin/env python3
"""
generate_models.py — Generate Power BI .SemanticModel + .Report folder pairs.

Usage:
    python generate_models.py                             # generate all configured models
    python generate_models.py --model financial_daily     # generate one model only
    python generate_models.py --list                      # list all configured models
    python generate_models.py --env d1v1                  # target environment (d1v1/c1v1/p1v1)
    python generate_models.py --model draw_sales --env p1v1

Configuration:  semantic.properties  (repo root)
Output:         output/models/       (SemanticModel + Report folder pairs)

Credentials (never stored in config):
    export SNOWFLAKE_USER=your.name@ourlotto.com    # SSO (recommended)
    export SNOWFLAKE_PASSWORD=your_password          # only for authenticator=snowflake
"""

import argparse
import sys
from pathlib import Path

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent))

from model_generator.config import load_config
from model_generator.snowflake_client import SnowflakeClient
from model_generator.model_generator import ModelGenerator

OUTPUT_DIR = Path(__file__).parent / "output" / "models"


def cmd_list(cfg) -> None:
    print(f"\n{'MODEL ID':<30} {'DISPLAY NAME':<40} {'FACT TABLE':<40} DIMENSIONS")
    print(f"{'-'*29} {'-'*39} {'-'*39} {'-'*30}")
    for mid, m in cfg.models.items():
        dims = ", ".join(m.dimensions)
        print(f"{mid:<30} {m.display_name:<40} "
              f"{m.fact_schema}.{m.fact_table:<35} {dims}")
    print()


def cmd_generate(cfg, model_ids: list[str], env: str | None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    env_label = f" (env: {env})" if env else ""
    print(f"\n{'='*65}")
    print(f"  pbi-automation  ·  model-generator{env_label}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*65}")

    with SnowflakeClient(cfg.snowflake) as sf:
        gen = ModelGenerator(cfg, sf)
        for model_id in model_ids:
            gen.generate(cfg.models[model_id], OUTPUT_DIR)

    print(f"\n  {len(model_ids)} model(s) generated in {OUTPUT_DIR}\n")
    print("  Next steps:")
    print("  1. Review output/models/ folders (.SemanticModel + .Report pairs)")
    print("  2. Copy both folders to lpc-v1-app-ldi-pbi-mos")
    print("  3. Run ALM Toolkit diff and open a PR")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Power BI .SemanticModel + .Report pairs from semantic.properties",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model",
        metavar="MODEL_ID",
        help="Generate only this model (use the [model.*] key from semantic.properties)",
    )
    parser.add_argument(
        "--env",
        metavar="ENV",
        default=None,
        help="Target environment: d1v1, c1v1, p1v1 "
             "(merges [snowflake.<env>] overrides from semantic.properties)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all configured models and exit",
    )
    parser.add_argument("--log", action="store_true", help="Write output to a timestamped log file in output/")
    args = parser.parse_args()

    if args.log:
        from _log import setup_file_logging
        log_path = setup_file_logging(output_dir="output")
        print(f"  Logging to {log_path}")

    try:
        cfg = load_config(env=args.env)
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        sys.exit(1)

    if args.list:
        cmd_list(cfg)
        return

    if args.model:
        if args.model not in cfg.models:
            known = ", ".join(cfg.models)
            print(
                f"\nERROR: model '{args.model}' not found in semantic.properties.\n"
                f"Known models: {known}\n",
                file=sys.stderr,
            )
            sys.exit(1)
        model_ids = [args.model]
    else:
        model_ids = list(cfg.models)

    try:
        cmd_generate(cfg, model_ids, args.env)
    except Exception as exc:
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
