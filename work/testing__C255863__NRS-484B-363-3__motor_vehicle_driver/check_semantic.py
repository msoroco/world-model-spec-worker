"""Check the exact draft semantic chain against the pinned runtime."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "runtime"), str(ROOT / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.semantic_delivery import validate


if __name__ == "__main__":
    assignment = json.loads((ROOT / "inputs" / FOLDER.name / "assignment.json").read_text())
    manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
    print(json.dumps(validate(FOLDER, assignment, manifest), sort_keys=True))
