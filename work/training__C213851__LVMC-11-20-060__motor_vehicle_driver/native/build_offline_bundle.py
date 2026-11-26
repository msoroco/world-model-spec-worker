"""Materialize exact inline CPU construction for the two sidewalk cases."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'
AID = ROOT.name
SUFFIXES = ('stop_before_sidewalk', 'cross_without_stop')
CAMERAS = (
    ('overview', 1920, 1080, 80),
    ('approach', 1280, 720, 80),
    ('reference_corner', 1280, 720, 75),
    ('driver_reference', 1280, 720, 80),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files_for(suffix):
    wrapper = '''"""Exact Native road-to-driveway entrypoint."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from runner import check, capture
if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        if not args.output_dir:
            raise SystemExit('Exact Native attempt directory required')
        print(json.dumps(capture(args.output_dir, SUFFIX, args.host, args.port)))
'''.replace('SUFFIX', repr(suffix))
    recording = next(c['recording_description'] for c in
                     json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
                     if c['case_id'] == AID + '__' + suffix)
    config = json.loads((NATIVE / suffix / 'config.json').read_text())
    config.update({
        'assignment_id': AID,
        'selected_case_id': AID + '__' + suffix,
        'supported_case_ids': [AID + '__' + name for name in SUFFIXES],
        'candidate_id': 'primary',
        'frame_count': 600,
        'required_atoms': ['ru.motor_vehicle', 'kin.position', 'kin.speed'],
        'source_packets': [],
        'cameras': [{'name': name, 'width': width, 'height': height,
                     'fov': fov, 'fov_deg': fov,
                     'pose_strategy': 'road-to-driveway sidewalk and driver view'}
                    for name, width, height, fov in CAMERAS],
        'case': {'case_id': AID + '__' + suffix,
                 'recording_description': recording},
    })
    files = [
        {'path': 'runner.py', 'content': wrapper},
        {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
        {'path': 'assignment-id.json', 'content':
         json.dumps({'assignment_id': AID}) + '\n'},
        {'path': 'native/selected-case.json', 'content':
         json.dumps({'suffix': suffix, 'case_id': AID + '__' + suffix}) + '\n'},
    ]
    for name in ('runner.py', 'build_requests.py', 'check_requests.py',
                 'check_road.py', 'measure_sidewalk.py', 'finalize.py'):
        files.append({'path': 'native/' + name,
                      'content': (NATIVE / name).read_text()})
    for name in SUFFIXES:
        for source in ('config.json', 'requested-tracks.jsonl'):
            path = NATIVE / name / source
            files.append({'path': f'native/{name}/{source}',
                          'content': path.read_text()})
    files.append({'path': 'native/road/road.xodr',
                  'content': (NATIVE / 'road/road.xodr').read_text()})
    tests = '''import json
import subprocess
import sys
import unittest
from pathlib import Path

class ExactBundle(unittest.TestCase):
    def test_selected_and_source_shape(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config.json').read_text())
        selected = json.loads((root / 'native/selected-case.json').read_text())
        self.assertEqual(config['selected_case_id'], selected['case_id'])
        result = subprocess.run([sys.executable, str(root / 'runner.py'), '--check'],
                                capture_output=True, text=True, check=True)
        proof = json.loads(result.stdout)
        self.assertTrue(proof['requests']['passed'])
        self.assertTrue(proof['road']['passed'])
        self.assertFalse(proof['carla_started'])

    def test_missing_source_rejected(self):
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'native'))
        from measure_sidewalk import measure
        with self.assertRaises(FileNotFoundError):
            measure(root, json.loads((root / 'config.json').read_text())['case_id'])
'''
    files.append({'path': 'tests/test_exact.py', 'content': tests})
    return files, recording


def build():
    entries = []
    for suffix in SUFFIXES:
        files, recording = files_for(suffix)
        construction = {'case_id': AID + '__' + suffix,
                        'law_id': 'LVMC-11-20-060', 'cell_id': 'C213851',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'files': files, 'recording_description': recording}
        path = NATIVE / suffix / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': construction['case_id'],
                        'construction': f'{suffix}/construction.json',
                        'construction_sha256': sha(path)})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': AID, 'cases': entries,
                'diagnostic_only': True}
    path = NATIVE / 'probe-offline-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest': str(path), 'cases': entries}


if __name__ == '__main__':
    print(json.dumps(build()))
