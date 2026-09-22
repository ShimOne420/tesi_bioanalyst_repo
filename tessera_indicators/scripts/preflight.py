#!/usr/bin/env python3
"""Fail fast if source/model provenance required for fine-tuning is incomplete."""

from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import load_task_config, unresolved_fields, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--tessera-root")
    parser.add_argument("--checkpoint")
    parser.add_argument("--output", default="artifacts/preflight.json")
    args = parser.parse_args()
    config = load_task_config(args.config)
    errors = {name: unresolved_fields(task) for name, task in config["tasks"].items()}
    errors = {name: values for name, values in errors.items() if values}
    checks = {
        "config": str(Path(args.config).resolve()),
        "tessera_root_exists": bool(args.tessera_root and Path(args.tessera_root).is_dir()),
        "checkpoint_exists": bool(args.checkpoint and Path(args.checkpoint).is_file()),
        "unresolved_task_fields": errors,
    }
    checks["ready_for_finetuning"] = not errors and checks["tessera_root_exists"] and checks["checkpoint_exists"]
    write_json(args.output, checks)
    if not checks["ready_for_finetuning"]:
        raise SystemExit("Preflight incomplete; see " + args.output)
    print("Preflight passed.")


if __name__ == "__main__":
    main()
