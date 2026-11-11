"""Check the canonical source-hashed semantic chain for six exposure cases."""

import json
from pathlib import Path

from worker_exchange.semantic_delivery import validate


root = Path(__file__).resolve().parent
assignment = json.loads((root.parents[1] / 'inputs' / root.name / 'assignment.json').read_text())
manifest = json.loads((root / 'probe-compatibility-manifest.json').read_text())
result = validate(root, assignment, manifest)
if result['selected_cases'] != 6:
    raise ValueError('All six exact exposure cases need semantic selection')
cases = json.loads((root / 'proposals/cases.json').read_text())
if len(cases['sweep_specs']) != 1 or cases['sweep_specs'][0]['status'] != 'incomplete':
    raise ValueError('Qualitative physical sweep must remain explicitly incomplete')
print(json.dumps(result, indent=2))
