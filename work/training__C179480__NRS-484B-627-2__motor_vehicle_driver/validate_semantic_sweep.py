"""Recheck the current C179480 semantic sweep and its indexed sources."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'runtime' / 'pipeline'))
from scenario_pipeline.batch_pipeline.stages import validate  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = HERE / 'proposals'
    index = read(root / 'semantic-index.json')
    for entry in index['stages'].values():
        for item in entry if isinstance(entry, list) else [entry]:
            path = HERE / item['path']
            if sha(path) != item['sha256']:
                raise ValueError('Semantic-index source hash changed: ' + str(path))
    binding = read(root / 'bindings.json')
    template = read(root / 'template.json')
    validate('bindings', deepcopy(binding), {
        'request': {'cell': {'cell_id': 'C179480'}, 'actor': 'motor_vehicle_driver',
                    'template_ids': [template['template_id']]},
    })
    for slug in ('traffic_movement', 'safe_operation', 'legal_compliance'):
        observable = read(root / ('judgment_observables_' + slug + '.json'))
        validate('judgment_observables', deepcopy(observable), {
            'request': {key: observable[key] for key in ('template_id', 'phrase', 'note')},
        })
        for item in template['structure']['judgment_calls_needed']:
            if item['phrase'] == observable['phrase']:
                item['observable_requirements'] = observable['observable_requirements']
    canonical = read(root / 'canonical-cases.json')
    validate('cases', deepcopy(canonical), {
        'request': {'cell': {'cell_id': 'C179480'}, 'actor': 'motor_vehicle_driver'},
        'dependencies': [binding], 'templates': [template],
    })
    specs = canonical['sweep_specs']
    if [(s['status'], s.get('planned_case_count', 0)) for s in specs] != [
        ('complete', 3), ('incomplete', 0), ('incomplete', 0)]:
        raise ValueError('Unexpected judgment sweep status or size')
    return {'validated': True, 'canonical_cases': len(canonical['cases']),
            'complete_sweep_cases': 3, 'incomplete_sweeps': 2,
            'index_sha256': sha(root / 'semantic-index.json'),
            'cases_sha256': sha(root / 'canonical-cases.json')}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2, sort_keys=True))
