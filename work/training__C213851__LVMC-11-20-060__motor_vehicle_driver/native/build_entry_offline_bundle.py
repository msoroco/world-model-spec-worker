"""Bind exact prospective roadway-return cases to source-shaped offline bundles."""

import hashlib
import json
from pathlib import Path

from build_entry_return import AID, POLICIES, ROOT
from build_offline_bundle import CAMERAS


NATIVE = ROOT / 'native'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wrapper(policy):
    return '''"""Exact Native return-to-roadway entrypoint."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from runner_entry_return import check_all, capture
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
        print(json.dumps(check_all()))
    else:
        if not args.output_dir:
            raise SystemExit('Exact Native attempt directory required')
        print(json.dumps(capture(args.output_dir, POLICY, args.host, args.port)))
'''.replace('POLICY', repr(policy))


def build(policy):
    folder = NATIVE / 'entry_return' / policy
    case_id = AID + '__' + policy
    config = json.loads((folder / 'config.json').read_text())
    config.update({
        'assignment_id': AID,
        'selected_case_id': case_id,
        'supported_case_ids': [AID + '__' + name for name in POLICIES],
        'candidate_id': 'primary',
        'frame_count': 1200,
        'required_atoms': ['ru.motor_vehicle', 'kin.position', 'kin.speed'],
        'source_packets': [],
        'cameras': [{'name': name, 'width': width, 'height': height,
                     'fov': fov, 'fov_deg': fov,
                     'pose_strategy': 'roadway return, sidewalk and driver view'}
                    for name, width, height, fov in CAMERAS],
    })
    files = [
        {'path': 'runner.py', 'content': wrapper(policy)},
        {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
        {'path': 'assignment-id.json', 'content': json.dumps({'assignment_id': AID}) + '\n'},
    ]
    for name in ('runner.py', 'runner_entry_return.py', 'build_entry_return.py',
                 'check_entry_return.py', 'build_requests.py', 'check_requests.py',
                 'check_road.py', 'measure_sidewalk.py',
                 'measure_entry_return.py', 'finalize_entry_return.py'):
        files.append({'path': 'native/' + name, 'content': (NATIVE / name).read_text()})
    for suffix in POLICIES:
        for name in ('config.json', 'requested-tracks.jsonl'):
            path = NATIVE / 'entry_return' / suffix / name
            files.append({'path': 'native/entry_return/' + suffix + '/' + name,
                          'content': path.read_text()})
    for suffix in ('stop_before_sidewalk', 'cross_without_stop'):
        for name in ('config.json', 'requested-tracks.jsonl'):
            path = NATIVE / suffix / name
            files.append({'path': 'native/' + suffix + '/' + name,
                          'content': path.read_text()})
    road = NATIVE / 'road/road.xodr'
    files.append({'path': 'native/road/road.xodr', 'content': road.read_text()})
    files.append({'path': 'tests/test_entry_request.py', 'content': '''import json
import subprocess
import sys
import unittest
from pathlib import Path

class EntryReturnRequest(unittest.TestCase):
    def test_exact_requested_motion(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'runner.py'), '--check'],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertTrue(value['requests']['passed'])
        self.assertTrue(value['road']['passed'])
        self.assertFalse(value['carla_started'])
'''})
    construction = {
        'case_id': case_id,
        'law_id': 'LVMC-11-20-060',
        'cell_id': 'C213851',
        'actor': 'motor_vehicle_driver',
        'entrypoint': 'runner.py',
        'files': files,
        'recording_description': {
            'channels': [
                {'name': 'ego_pose_speed_footprint', 'unit': 'structured',
                 'sampling_rate_hz': 20,
                 'method': 'original frame-joined ego pose, speed and bounding box',
                 'time_window': 'entire 60 s original Native capture',
                 'reference_frame': 'source-verified map and original frame times',
                 'uncertainty': '50 ms sampling; physical and pixel review pending'},
                {'name': 'approaching_vehicle_trace', 'unit': 'structured',
                 'sampling_rate_hz': 20,
                 'method': 'original frame-joined approaching vehicle pose and speed',
                 'time_window': 'entire 60 s original Native capture',
                 'reference_frame': 'source-verified roadway lane and original frame times',
                 'uncertainty': '50 ms sampling; physical and pixel review pending'},
                {'name': 'pedestrian_trace', 'unit': 'structured',
                 'sampling_rate_hz': 20,
                 'method': 'original frame-joined separate pedestrian pose',
                 'time_window': 'entire 60 s original Native capture',
                 'reference_frame': 'source-verified sidewalk and original frame times',
                 'uncertainty': '50 ms sampling; physical and pixel review pending'},
            ],
            'context_inputs': [
                {'name': 'roadway_entry_geometry', 'unit': 'structured',
                 'method': 'source-verified authored road and original site review'},
                {'name': 'sidewalk_geometry', 'unit': 'structured',
                 'method': 'source-verified sidewalk polygon and driveway edge'},
            ],
            'limitations': [
                'Requested route and traffic timing are diagnostic controller targets.',
                'Actual Native motion, body overlap, pixel visibility and legal necessity are unverified.',
            ],
        },
    }
    target = folder / 'construction.json'
    target.write_text(json.dumps(construction, indent=2) + '\n')
    dispositions = json.loads((ROOT / 'case-plan.json').read_text())[
        'requirement_dispositions']
    contract = {
        'format': 'worker-measurement-contract',
        'case_id': case_id,
        'requirements': [
            {'disposition_index': 0, 'requirement': dispositions[0]['requirement'],
             'source': dispositions[0]['source'],
             'output_key': 'roadway_entry_observation',
             'method': 'measure_roadway_return', 'value_type': 'object',
             'kind': 'measured',
             'inputs': ['native-rows.jsonl', 'captured-source-hashes.json',
                        'trace.jsonl', 'capture/evidence.jsonl',
                        'capture/native/frames.jsonl',
                        'original-entry-site-review.json']},
            {'disposition_index': 2, 'requirement': dispositions[2]['requirement'],
             'source': dispositions[2]['source'],
             'output_key': 'site_scope_context',
             'method': 'source_verified_entry_site', 'value_type': 'object',
             'kind': 'sourced_context',
             'inputs': ['original-site-review.json',
                        'original-entry-site-review.json', 'site-review.json',
                        'road.xodr', 'site-sources/district.json',
                        'site-sources/driveway.json',
                        'site-sources/sidewalk.json',
                        'site-sources/pedestrian.json']},
        ],
        'negative': {'remove': ['original-entry-site-review.json'],
                     'error_contains':
                         'Missing required source: original-entry-site-review.json'},
    }
    contract_path = folder / 'measurement-contract.json'
    contract_path.write_text(json.dumps(contract, indent=2) + '\n')
    return {'case_id': case_id,
            'construction': policy + '/construction.json',
            'construction_sha256': sha(target),
            'measurement_contract': policy + '/measurement-contract.json',
            'measurement_procedure':
                {'entrypoint': 'native/finalize_entry_return.py'}}


def main():
    cases = [build(policy) for policy in POLICIES]
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': AID, 'cases': cases,
                'diagnostic_only': True}
    path = NATIVE / 'entry_return/offline-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    repo = ROOT.parents[1]
    public = {
        'format': 'worker-execution-manifest',
        'assignment_id': AID,
        'runtime_manifest_sha256': sha(repo / 'runtime/SOURCE-MANIFEST.json'),
        'cases': [],
        'diagnostic_only': True,
    }
    for case in cases:
        policy = case['case_id'].rsplit('__', 1)[-1]
        public['cases'].append({
            'case_id': case['case_id'],
            'construction': 'native/entry_return/' + policy + '/construction.json',
            'construction_sha256': case['construction_sha256'],
            'measurement_contract':
                'native/entry_return/' + policy + '/measurement-contract.json',
            'measurement_procedure': case['measurement_procedure'],
            'fixture_recipe':
                f'work/{AID}/native/entry_return/{policy}/diagnostic/fixture-recipe.json',
        })
    public_path = ROOT / 'entry-return-compat-manifest.json'
    public_path.write_text(json.dumps(public, indent=2) + '\n')
    return {'manifest': str(path.relative_to(ROOT)),
            'public_manifest': str(public_path.relative_to(ROOT)), 'cases': cases}


if __name__ == '__main__':
    print(json.dumps(main()))
