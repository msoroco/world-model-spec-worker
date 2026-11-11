"""Check the canonical source-hashed semantic chain for six exposure cases."""

import json
from pathlib import Path

from worker_exchange.semantic_delivery import validate


root = Path(__file__).resolve().parent
assignment = json.loads((root.parents[1] / 'inputs' / root.name / 'assignment.json').read_text())
manifest = json.loads((root / 'probe-compatibility-manifest.json').read_text())
result = validate(root, assignment, manifest)
if result['selected_cases'] != 9:
    raise ValueError('All nine exact exposure cases need semantic selection')
cases = json.loads((root / 'proposals/cases.json').read_text())
if len(cases['sweep_specs']) != 1 or cases['sweep_specs'][0]['status'] != 'complete':
    raise ValueError('Finite qualitative physical sweep must be complete')
print(json.dumps(result, indent=2))
