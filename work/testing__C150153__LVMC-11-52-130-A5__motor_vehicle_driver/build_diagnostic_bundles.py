"""Build exact, source-labeled CPU diagnostic bundles for the elevator branch.

These bundles exercise package materialization and engineering construction.
They cannot be selected as reviewed Native captures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PLAN = HERE / 'case-plan.json'

RUNNER = '''"""Exact C150153 diagnostic preflight; original capture requires reviewed sources."""
import argparse
import hashlib
import json
from pathlib import Path
from parking import CASES, target_body_interval, validate_site

def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'scene.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != scene['case_plan_sha256']:
        raise ValueError('case plan source changed')
    plan = json.loads(raw)
    if scene['case_id'] not in {item['case_id'] for item in plan['cases']}:
        raise ValueError('exact case absent from plan')
    if config['selected_case_id'] != scene['case_id'] or scene['case_id'] != scene['assignment_id'] + '__' + scene['kind']:
        raise ValueError('selected exact case differs')
    if config['rate_hz'] * config['duration_s'] != 900 or len(config['cameras']) != 4:
        raise ValueError('capture specification differs')
    site = scene['diagnostic_site']
    validate_site(site)
    case = next(c for c in CASES if c.id == scene['kind'])
    interval = target_body_interval(site, case, scene['body_length_m'])
    if abs(interval[0] - scene['target_body_interval_m'][0]) > 1e-9 or abs(interval[1] - scene['target_body_interval_m'][1]) > 1e-9:
        raise ValueError('case target differs')
    return scene

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    scene = check()
    if not args.check:
        raise ValueError('Diagnostic-only context cannot create an original Native capture')
    print('exact diagnostic preflight passed: ' + scene['case_id'])

if __name__ == '__main__':
    main()
'''

TEST = '''import unittest
from unittest.mock import patch
import runner

class BundleTest(unittest.TestCase):
    def test_exact_preflight(self):
        self.assertEqual(runner.check()['source_kind'], 'synthetic_diagnostic')

    def test_native_capture_is_refused(self):
        with patch('sys.argv', ['runner.py', '--output-dir', '.']):
            with self.assertRaisesRegex(ValueError, 'Diagnostic-only'):
                runner.main()

if __name__ == '__main__':
    unittest.main()
'''


def _json(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _site(fallback=False):
    marker = '0' * 64
    return {'cell_id': 'C150153', 'layout': 'one_way_road', 'map_sha256': marker,
            'municipal_jurisdiction_sha256': marker, 'sidewalk_sha256': marker,
            'fixture_identity_sha256': marker, 'fixture_geometry_sha256': marker,
            'curb_sha256': marker, 'one_way_direction_sha256': marker,
            'fixture_blueprint_sha256': marker, 'fixture_kind': 'sidewalk_elevator',
            'fixture_physical_support': 'spawned_prop',
            'fixture': {'west_x_m': 10.0, 'east_x_m': 12.0, 'curb_y_m': 0.0,
                        'sidewalk_depth_m': 2.0}, 'curb_y_m': 0.0,
            'approach_waypoints': [[0.0, 0.0], [20.0, 0.0]],
            'ego_blueprint_sha256': marker, 'camera_plan_sha256': marker,
            'traffic_conflict_source_sha256': marker,
            'police_direction_source_sha256': marker,
            'traffic_device_source_sha256': marker,
            'diagnostic_camera_lateral_offset_m': 3.0 if fallback else 2.0}


def build():
    import importlib.util
    spec = importlib.util.spec_from_file_location('parking', HERE / 'parking.py')
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules['parking'] = module
    spec.loader.exec_module(module)
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    rows = []
    for item in plan['cases']:
        case_id = item['case_id']
        kind = case_id.removeprefix(ASSIGNMENT + '__')
        case = next(c for c in module.CASES if c.id == kind)
        candidates = []
        for fallback in (False, True):
            site = _site(fallback)
            scene = {'assignment_id': ASSIGNMENT, 'case_id': case_id, 'kind': kind,
                     'source_kind': 'synthetic_diagnostic', 'case_plan_sha256': _sha(plan_bytes),
                     'diagnostic_site': site, 'body_length_m': 4.5,
                     'target_body_interval_m': module.target_body_interval(site, case, 4.5),
                     'candidate_id': 'fallback1' if fallback else 'primary'}
            config = {'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                      'actor': 'motor_vehicle_driver', 'selected_case_id': case_id,
                      'rate_hz': 20, 'duration_s': 45,
                      'required_atoms': [], 'source_packets': [],
                      'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                      'case': {'kind': kind, 'region': case.region,
                               'activity': case.activity, 'exception': case.exception},
                      'diagnostic_camera_lateral_offset_m': site['diagnostic_camera_lateral_offset_m']}
            files = {'runner.py': RUNNER, 'parking.py': (HERE / 'parking.py').read_text(),
                     'scene.json': _json(scene), 'config.json': _json(config),
                     'case-plan.json': plan_bytes.decode(), 'tests/test_bundle.py': TEST}
            construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                            'actor': config['actor'], 'case_id': case_id,
                            'entrypoint': 'runner.py', 'diagnostic_only': True,
                            'recording_description': item['recording_description'],
                            'files': [{'path': path, 'content': content} for path, content in files.items()]}
            name = 'construction-diagnostic-' + kind + ('-fallback1' if fallback else '') + '.json'
            (HERE / name).write_text(_json(construction), encoding='utf-8')
            candidates.append({'id': 'fallback1' if fallback else 'primary',
                               'construction': name, 'construction_sha256': _sha((HERE / name).read_bytes())})
        rows.append({'case_id': case_id, 'kind': item['kind'],
                     'construction': candidates[0]['construction'],
                     'construction_sha256': candidates[0]['construction_sha256'],
                     'candidate_risk': {'status': 'physical', 'reason': 'The fixture or camera view may fail physical readback.'},
                     'candidates': [{**candidates[1],
                         'trigger': {'source': 'original fixture and camera readback',
                                     'metric': 'fixture visibility', 'failure_condition': 'fixture not visible'},
                         'changed_knobs': ['camera lateral offset 2.0 m to 3.0 m']}]})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'status': 'diagnostic_only_no_reviewed_site', 'cases': rows}
    (HERE / 'execution-manifest.diagnostic.json').write_text(_json(manifest), encoding='utf-8')
    print(f'built {len(rows)} exact diagnostic primary/fallback bundles')


if __name__ == '__main__':
    build()
