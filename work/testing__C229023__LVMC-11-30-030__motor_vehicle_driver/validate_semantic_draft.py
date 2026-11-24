"""Validate the source-bound draft stages against the pinned active runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not output or not Path(output).resolve().is_relative_to((ROOT / ".runtime-work").resolve()):
    raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from scenario_pipeline.worker_exchange import semantic_delivery

assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
print(json.dumps(semantic_delivery.validate(HERE, assignment, manifest), sort_keys=True))
