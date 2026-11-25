"""Validate selected semantic stages and exact delivery handoffs on current runtime."""
import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work' / 'owner150142' / 'semantic-delivery'))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.semantic_delivery import validate as semantic
from worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assignment = REPO / 'inputs' / HERE.name / 'assignment.json'
source = json.loads(assignment.read_text())
manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
semantic_result = semantic(HERE, source, manifest)
cases = []
for entry in manifest['cases']:
    validate_case(HERE, entry, source.get('selection_targets'))
    cases.append({'case_id': entry['case_id'],
                  'construction_sha256': entry['construction_sha256'],
                  'delivery_test_log_sha256':
                  entry['delivery_acceptance']['test_log_sha256'],
                  'delivery_negative_log_sha256':
                  entry['delivery_acceptance']['negative_log_sha256']})
assert len(cases) == 30
proof = {'format': 'c150142-selected-semantic-delivery-v1',
         'passed': True, 'assignment_sha256': sha(assignment),
         'manifest_sha256': sha(manifest_path),
         'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
         'semantic': semantic_result, 'delivery_cases': cases,
         'physical_acceptance_claimed': False,
         'original_native_observed': False}
path = HERE / 'current-selected-semantic-delivery-proof.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'cases': len(cases), 'proof_sha256': sha(path)}, sort_keys=True))
