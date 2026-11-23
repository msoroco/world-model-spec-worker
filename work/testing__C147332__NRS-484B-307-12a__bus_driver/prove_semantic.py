"""Run pinned semantic delivery validator on the exact permission proposals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if not output_root.is_relative_to((REPO / '.runtime-work').resolve()):
    raise ValueError('SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work')
sys.path.insert(0, str((REPO / 'runtime/scenario_pipeline').resolve()))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
validate(ROOT, assignment, manifest)
print('pinned semantic delivery validation passed')
