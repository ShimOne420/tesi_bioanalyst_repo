#!/usr/bin/env python3
"""Build the audited input that a future BioMAP Map-to-Text layer may consume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=("bii", "msa_globio4"))
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raster", default="PENDING_RASTER_OUTPUT")
    parser.add_argument("--model-version", default="PENDING_MODEL_VERSION")
    args = parser.parse_args()
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    payload = {
        "schema_version": "1.0",
        "indicator": args.task,
        "claim": "Supervised TESSERA estimate of the declared official target map; not an independent canonical calculation.",
        "model_version": args.model_version,
        "raster": args.raster,
        "metrics": metrics,
        "required_user_response_fields": ["selected_area", "period", "indicator_value", "uncertainty", "valid_coverage", "sources", "limitations"],
        "decision_guardrail": "Do not turn this context into a recommendation without exposing uncertainty, coverage, and source provenance.",
    }
    write_json(args.output, payload)
    print(args.output)


if __name__ == "__main__":
    main()
