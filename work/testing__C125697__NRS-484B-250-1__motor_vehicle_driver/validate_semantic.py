"""Validate this assignment's source-hashed canonical draft stages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from worker_exchange.semantic_delivery import validate  # noqa: E402


def main() -> None:
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
    print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
