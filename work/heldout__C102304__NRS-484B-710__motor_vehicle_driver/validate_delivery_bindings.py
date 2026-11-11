"""Validate all source-hashed semantic and exact-case CPU acceptance bindings."""
import json
import sys
from pathlib import Path
folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case
assignment = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
manifest = json.loads((folder / 'execution-manifest.json').read_text())
print(json.dumps(validate_semantic(folder, assignment, manifest), sort_keys=True))
for entry in manifest['cases']:
    validate_case(folder, entry, assignment.get('selection_targets'))
print('validated_delivery_acceptance_cases', len(manifest['cases']))
