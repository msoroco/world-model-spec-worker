"""Run the pinned physical event assessor on an inventoried CPU fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import assess_physical

    config = json.loads((args.fixture / "config.json").read_text())
    report = assess_physical(args.fixture, config)
    report.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(report["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
