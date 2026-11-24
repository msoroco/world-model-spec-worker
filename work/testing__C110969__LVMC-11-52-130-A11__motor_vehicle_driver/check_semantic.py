"""Validate the owned draft semantic chain against the pinned current runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from scenario_pipeline.worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    selected = {row["case_id"]: row for row in manifest["cases"]}
    if len(selected) != 7:
        raise ValueError("Seven exact selected constructions required")
    report = validate(HERE, assignment, manifest)
    if report["selected_cases"] != 7 or report["stage_count"] != 8:
        raise ValueError("Canonical semantic coverage changed")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
