"""Bind the three speed attempts to distinct inline Native constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C230259__NRS-484B-600-1e__motor_vehicle_driver'
TARGETS = {'probe_01': 75.0, 'probe_02': 80.0, 'probe_03': 85.0}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    source = HERE/'selected_primary'
    entries = []
    for probe, target in TARGETS.items():
        case = AID + '__' + probe
        bundle = HERE/('selected_primary' if probe == 'probe_03' else probe)
        if probe != 'probe_03':
            bundle.mkdir(exist_ok=True)
            (bundle/'tests').mkdir(exist_ok=True)
            runner = (source/'runner.py').read_text().replace('probe_03', probe).replace('85.0*MPS_PER_MPH', f'{target}*MPS_PER_MPH')
            config = json.loads((source/'config.json').read_text())
            config['case_id'] = case
            config['selected_case_id'] = case
            config['recording_description'] = config['recording_description'].replace('85 mph', f'{target:g} mph')
            (bundle/'runner.py').write_text(runner)
            write(bundle/'config.json', config)
            (bundle/'tests/test_bundle.py').write_text((source/'tests/test_bundle.py').read_text())
        names = ('runner.py', 'config.json', 'tests/test_bundle.py')
        files = [{'path': name, 'content': (bundle/name).read_text()} for name in names]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C230259', 'law_id': 'NRS-484B-600-1e',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'recording_description': json.loads((bundle/'config.json').read_text())['recording_description'],
                        'files': files}
        path = HERE/f'{probe}-construction.json'
        write(path, construction)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({'case_id': case, 'construction': path.name,
                        'construction_sha256': digest,
                        'candidate_risk': {'status': 'physical' if probe == 'probe_03' else 'none',
                                           'reason': 'Requested speed may not be achieved on a reviewed clear route' if probe == 'probe_03' else 'Lower speed attempt has no identified additional construction risk'},
                        'candidates': []})
    manifest = {'assignment_id': AID, 'cases': entries}
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'constructions': {entry['case_id']: entry['construction_sha256'] for entry in entries}}, sort_keys=True))


if __name__ == '__main__':
    main()
