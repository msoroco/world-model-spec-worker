"""Validate authored canonical binding and case proposals under the pinned runtime."""
import hashlib
import json
import os
from pathlib import Path
import sys

if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '').endswith('/.runtime-work/c110763-semantic-cases'):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT to .runtime-work/c110763-semantic-cases')
sys.path.insert(0, 'runtime/pipeline')
from scenario_pipeline.batch_pipeline import stages  # noqa: E402

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'


def load(name):
    return json.loads((PROPOSALS / name).read_text())


def digest(name):
    return hashlib.sha256((PROPOSALS / name).read_bytes()).hexdigest()


template = load('template.json')
template['structure']['judgment_calls_needed'] = [
    dict(judgment, observable_requirements=load(f'judgment-observables-{index}.json')['observable_requirements'])
    for index, judgment in enumerate(template['structure']['judgment_calls_needed'], 1)
]
bindings = load('bindings.json')
cases = load('cases.json')
request = {'cell': {'cell_id': 'C110763'}, 'actor': 'motor_vehicle_driver',
           'template_ids': [template['template_id']]}
stages.validate('bindings', bindings, {'request': request, 'canonical_parameter_rules': {},
                                      'dependencies': [template]})
stages.validate('cases', cases, {'request': request, 'dependencies': [bindings],
                                'templates': [template]})
proof = {
    'format': 'canonical-cases-check-v1',
    'assignment_id': 'training__C110763__NRS-484B-113-2__motor_vehicle_driver',
    'binding_sha256': digest('bindings.json'), 'cases_sha256': digest('cases.json'),
    'cases_stage_validated': True, 'case_count': len(cases['cases']),
    'incomplete_sweep_plan_count': len(cases['sweep_specs']),
    'physical_observation_claimed': False,
    'remaining': 'Complete physical sweep specs with source-grounded ranges; prove requested deterministic branch, independent acceptance and comparison against original Native sources.',
}
(PROPOSALS / 'canonical-cases-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof, indent=2))
