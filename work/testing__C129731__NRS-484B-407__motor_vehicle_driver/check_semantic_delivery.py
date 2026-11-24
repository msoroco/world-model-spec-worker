"""Validate the selected semantic stage chain against its exact constructions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.semantic_delivery import validate


def main() -> None:
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
