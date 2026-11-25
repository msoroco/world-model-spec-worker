"""Validate the draft law/cell stage chain against exact paired constructions."""
import json
import os
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = next(p for p in PACKAGE.parents if (p / 'batch.json').is_file())
output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not output_root.is_relative_to(ROOT / '.runtime-work'):
    raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
manifest = {'cases': [
    {'case_id': PACKAGE.name + '__probe_1',
     'construction': 'draft-primary/construction.json'},
    {'case_id': PACKAGE.name + '__probe_2',
     'construction': 'draft-controlled/construction.json'}
]}
print(json.dumps(validate(PACKAGE, assignment, manifest), sort_keys=True))
