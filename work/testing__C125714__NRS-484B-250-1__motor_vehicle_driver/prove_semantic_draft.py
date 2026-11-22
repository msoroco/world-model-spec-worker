"""Validate exact draft semantic stages against the pinned CPU runtime."""
import json
from pathlib import Path

from scenario_pipeline.worker_exchange.semantic_delivery import validate


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    result = validate(ROOT, assignment, manifest)
    print(json.dumps({**result, "diagnostic_only": True}))


if __name__ == "__main__":
    main()
