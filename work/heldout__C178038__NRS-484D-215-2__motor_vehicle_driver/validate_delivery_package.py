"""Run pinned CPU validators over the six-case partial delivery package."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.execution_manifest import validate as validate_execution
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts

assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
manifest = validate_execution(ROOT, HERE.name)
semantic = validate_semantic(HERE, assignment, manifest)
for entry in manifest['cases']:
    validate_case(HERE, entry, assignment.get('selection_targets'))
check_receipts(ROOT, HERE, manifest)
print(json.dumps({'exact_cases': len(manifest['cases']),
                  'semantic_stages': semantic['stage_count'],
                  'physical_preparation': 'synthetic fixture proofs passed',
                  'delivery_acceptance': 'synthetic positive and negative proofs passed',
                  'compatibility_receipts': 'source-bound static verification passed',
                  'physical_acceptance_claimed': False,
                  'legal_acceptance_claimed': False}, indent=2))
