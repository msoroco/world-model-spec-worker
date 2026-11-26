"""Materialize two independent Native driveway comparison constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C150094__LVMC-11-52-130-A7__motor_vehicle_driver'
VARIANTS = {'01': {'gap_m': 2.0, 'authority': False},
            '03': {'gap_m': 1.2, 'authority': True}}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = HERE / 'selected_primary'
    entries = [entry for entry in json.loads((HERE / 'selected-offline-manifest.json').read_text())['cases']
               if entry['case_id'].endswith('__probe_02')]
    for probe, variant in VARIANTS.items():
        case = AID + '__probe_' + probe
        bundle = HERE / ('probe_' + probe)
        bundle.mkdir(exist_ok=True)
        runner = (original / 'runner.py').read_text().replace('__probe_02', '__probe_' + probe)
        (bundle / 'runner.py').write_text(runner)
        (bundle / 'finalize.py').write_text((original / 'finalize.py').read_text())
        config = json.loads((original / 'config.json').read_text())
        config['case_id'] = case
        config['selected_case_id'] = case
        config['supported_case_ids'] = [case]
        config['case']['case_id'] = case
        config['target_gap_m'] = variant['gap_m']
        config['case'] = {'case_id': case,
                          'recording_description': config['recording_description'],
                          'branch': 'far-no-exception' if probe == '01' else 'near-private-authority'}
        write(bundle / 'config.json', config)
        tests = (original / 'tests/test_bundle.py').read_text()
        (bundle / 'tests').mkdir(exist_ok=True)
        (bundle / 'tests/test_bundle.py').write_text(tests)
        names = ('runner.py', 'config.json', 'finalize.py', 'measure_driveway.py', 'tests/test_bundle.py')
        files = [{'path': name, 'content': ((HERE / name) if name == 'measure_driveway.py' else (bundle / name)).read_text()} for name in names]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C150094', 'law_id': 'LVMC-11-52-130-A7',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'recording_description': config['recording_description'], 'files': files}
        path = HERE / ('selected-construction-probe_' + probe + '.json')
        write(path, construction)
        entries.append({'case_id': case, 'construction': path.name,
                        'construction_sha256': sha(path), 'candidate_risk': {
                            'status': 'none', 'reason': 'No original route or camera failure is measured for this exact comparison case'},
                        'candidates': []})
    write(HERE / 'selected-offline-manifest.json', {'assignment_id': AID, 'cases': entries})
    print(json.dumps({row['case_id']: row['construction_sha256'] for row in entries}, sort_keys=True))


if __name__ == '__main__':
    main()
