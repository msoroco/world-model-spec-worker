"""Replay the pinned canonical semantic stage validator for this assignment."""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not output_root.is_relative_to(ROOT / '.runtime-work'):
    raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
manifest = json.loads((HERE / 'execution-manifest.json').read_text())
print(json.dumps(validate(HERE, assignment, manifest), indent=2))
