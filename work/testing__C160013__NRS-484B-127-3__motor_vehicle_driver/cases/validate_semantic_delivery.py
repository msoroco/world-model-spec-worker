"""Validate the exact canonical semantic chain against the current manifest."""
import json
import os
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not root.is_relative_to((REPO / '.runtime-work').resolve()):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((REPO / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
print(json.dumps(validate(PACKAGE, assignment, manifest), sort_keys=True))
