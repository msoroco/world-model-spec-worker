"""Validate authored stage chain against pinned CPU stage contracts."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT','')).resolve()
if not output.is_relative_to(REPO/'.runtime-work'):
    raise ValueError('export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate
assignment = json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
manifest = json.loads((ROOT/'execution-manifest.json').read_text())
print(json.dumps(validate(ROOT, assignment, manifest), indent=2))
