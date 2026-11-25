"""Expand the pinned signed-zone Native survey gate to below, at, and above requests.

Each construction keeps the same physical route and source contract. The request
offset is a controller input; observed velocity and sign authority remain sources.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C179819__NRS-484B-620-2__motor_vehicle_driver'
CASES = (('probe_01', '-5.0'), ('probe_02', '0.0'), ('probe_03', '5.0'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    source = HERE / 'selected_primary'
    manifest = {'assignment_id': AID, 'cases': []}
    for suffix, offset in CASES:
        case_id = AID + '__' + suffix
        bundle = HERE / 'three' / suffix / 'primary'
        for name in ('runner.py', 'config.json', 'tests/test_bundle.py'):
            content = (source / name).read_text().replace('__probe_03', '__' + suffix)
            if name == 'runner.py':
                content = content.replace("(survey['authorized_mph']+5.0)*MPS_PER_MPH",
                                          "(survey['authorized_mph']+" + offset + ")*MPS_PER_MPH")
                if offset != '5.0' and "(survey['authorized_mph']+" + offset + ")*MPS_PER_MPH" not in content:
                    raise ValueError('Speed request replacement failed')
            if name == 'config.json':
                obj = json.loads(content)
                obj['case'] = 'signed-zone-requested-' + {'probe_01': 'below', 'probe_02': 'at', 'probe_03': 'above'}[suffix]
                obj['target_offset_mph'] = float(offset)
                content = json.dumps(obj, indent=2) + '\n'
            path = bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        names = ('runner.py', 'config.json', 'tests/test_bundle.py')
        construction = {'format': 'worker-construction', 'assignment_id': AID,
            'case_id': case_id, 'cell_id': 'C179819', 'law_id': 'NRS-484B-620-2',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'recording_description': json.loads((bundle / 'config.json').read_text())['recording_description'],
            'files': [{'path': name, 'content': (bundle / name).read_text()} for name in names]}
        target = HERE / 'three' / suffix / 'primary-construction.json'
        write(target, construction)
        manifest['cases'].append({'case_id': case_id,
            'construction': str(target.relative_to(HERE)),
            'construction_sha256': sha(target),
            'candidate_risk': {'status': 'physical',
                'reason': 'Surveyed signed-zone route and commanded speed may fail to produce source-verified zone traversal and stable observed speed'},
            'candidates': []})
    write(HERE / 'three-offline-manifest.json', manifest)
    print(json.dumps({r['case_id']: r['construction_sha256'] for r in manifest['cases']}, sort_keys=True))


if __name__ == '__main__':
    main()
