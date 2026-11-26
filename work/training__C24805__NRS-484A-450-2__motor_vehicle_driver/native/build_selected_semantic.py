"""Bind C24805's two no-reference cases to canonical draft stage proposals."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SOURCE = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver/proposals'
TARGET = HERE / 'proposals'
OLD = 'training__C111325__NRS-484A-450-2__motor_vehicle_driver'
NEW = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(value):
    if isinstance(value, str):
        return (value.replace(OLD, NEW).replace('C111325', 'C24805')
                .replace('sight_stop', 'probe_a')
                .replace('sight_pass', 'probe_b'))
    if isinstance(value, list):
        return [change(item) for item in value]
    if isinstance(value, dict):
        return {key: change(item) for key, item in value.items()}
    return value


def build():
    TARGET.mkdir(exist_ok=True)
    stages = {}
    for name in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases'):
        body = change(json.loads((SOURCE / f'{name}.json').read_text()))
        if name == 'cases':
            body['cases'] = [case for case in body['cases']
                             if case['case_id'] in (NEW + '__baseline_reference', NEW + '__probe_a', NEW + '__probe_b')]
            if len(body['cases']) != 3:
                raise ValueError('Exact no-reference semantic cases missing')
            for case in body['cases']:
                if case['target_type'] == 'baseline':
                    case['rationale'] = 'Shared no-reference signed approach context; no extra recording'
                    case['variable_assignments']['near_side_crosswalk_present']['value'] = False
                    case['variable_assignments']['requested_pre_crosswalk_stop']['value'] = None
                else:
                    case['paired_probe_id'] = NEW + '__comparison'
        elif name == 'bindings':
            body['established_contexts'][0]['name'] = 'C24805 no-reference blind intersection approach'
        target = TARGET / f'{name}.json'
        target.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')
        stages[name] = {'path': f'proposals/{name}.json', 'sha256': sha(target)}
    stages['judgment_observables'] = []
    index = {'format': 'worker-semantic-delivery', 'assignment_id': NEW,
             'status': 'draft', 'stages': stages}
    target = TARGET / 'semantic-index.json'
    target.write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'case_count': 2, 'index_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    build()
