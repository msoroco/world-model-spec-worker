"""Validate source-hashed draft stages against the current pinned runtime."""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or REPO / ".runtime-work" not in Path(output).resolve().parents:
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
print(json.dumps(validate(HERE, assignment, manifest), sort_keys=True))
