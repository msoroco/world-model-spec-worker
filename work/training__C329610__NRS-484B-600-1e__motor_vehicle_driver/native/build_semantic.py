"""Adapt the canonical speed-stage proposals to the exact C329610 turn cell."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
SOURCE = ROOT.parent/'training__C230259__NRS-484B-600-1e__motor_vehicle_driver'/'proposals'
DEST = ROOT/'proposals'
DEST.mkdir(exist_ok=True)


def transform(value):
    if isinstance(value, dict):
        return {key: transform(item) for key, item in value.items()}
    if isinstance(value, list):
        return [transform(item) for item in value]
    if isinstance(value, str):
        for old, new in (('training__C230259__NRS-484B-600-1e__motor_vehicle_driver', AID),
                         ('C230259', 'C329610'), ('probe_01', 'probe_a'),
                         ('probe_02', 'probe_at'), ('probe_03', 'probe_b'),
                         ('authored two-lane 1,800 m road corridor',
                          'source-hashed two-way C329610 intersection with left-turn route 1,13,4')):
            value = value.replace(old, new)
        return value
    return value


def main():
    stages = {}
    for name in ('relevance', 'relevance-batch', 'template', 'bindings', 'cases'):
        obj = transform(json.loads((SOURCE/(name+'.json')).read_text()))
        if name == 'cases':
            for case in obj['cases']:
                if case['case_id'].endswith(('probe_a','probe_at','probe_b')):
                    case['rationale'] += ' C329610 left-turn road sequence 1,13,4 is mandatory.'
                    suffix = case['case_id'].removeprefix(AID+'__')
                    construction = json.loads((ROOT/('selected-'+suffix+'-primary-construction.json')).read_text())
                    case['recording_description'] = construction['recording_description']
        path = DEST/(name+'.json')
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
        stages['relevance_batch' if name == 'relevance-batch' else name] = {
            'path': 'proposals/'+path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    stages['judgment_observables'] = []
    (DEST/'semantic-index.json').write_text(json.dumps({
        'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': stages},
        indent=2) + '\n')


if __name__ == '__main__':
    main()
