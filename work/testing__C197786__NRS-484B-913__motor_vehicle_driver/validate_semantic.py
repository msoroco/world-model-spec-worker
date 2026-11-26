"""Validate exact draft stage chain against the pinned worker runtime."""

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime"))
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from scenario_pipeline.worker_exchange.semantic_delivery import validate


assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
manifest = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))
