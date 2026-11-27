"""Rebuild exact selected inline constructions after source changes."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PREFIX = ASSIGNMENT + '__selected_ed45c8e4__condition_'
FILES = ('runner.py', 'finalize.py', 'native/runner.py', 'native/geometry.py',
         'native/acquisition.py', 'native/controlled_access_yield.py',
         'native/multi_traffic_yield.py')
CAMERAS = [dict(name=name, width=width, height=height,
                pose_strategy='original Native entry and approaching highway traffic', fov_deg=95)
           for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                       ('reference_corner', 1280, 720),
                                       ('driver_reference', 1280, 720))]
CHANNELS = [dict(name=term, unit='structured', sampling_rate_hz=20,
                 method='source-bound original Native actor/map/camera readback',
                 time_window='600 frames', reference_frame='authored road/junction and Native world XY',
                 uncertainty='50 ms sampling; legal status, immediate hazard and reasonable safety require review')
            for term in ('st.controlled_access', 'drv.entering_intersection', 'drv.lane_change',
                         'drv.approaching', 'drv.time_to_conflict', 'rel.surface_gap',
                         'drv.yields_to', 'drv.hard_deceleration',
                         'original_entry_and_traffic_history', 'entry_yield_and_clearance')]
TEST = '''import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check
class SelectedConstruction(unittest.TestCase):
    def test_exact_identity_and_geometry(self):
        config = json.loads(Path('config.json').read_text())
        report = check(config)
        self.assertEqual(report['case_id'], config['case_id'])
        self.assertEqual(report['camera_views'], [v['name'] for v in config['cameras']])
        self.assertFalse(report['physical_success_claimed'])
    def test_reject_wrong_case(self):
        config = json.loads(Path('config.json').read_text())
        config['case_id'] += '__wrong'
        with self.assertRaisesRegex(ValueError, 'exact selected entry case'):
            check(config)
'''


def make(suffix):
    case = PREFIX + suffix
    config = {
        'assignment_id': ASSIGNMENT, 'case_id': case, 'selected_case_id': case,
        'law_id': 'NRS-484B-263', 'cell_id': 'C177626', 'actor': 'motor_vehicle_driver',
        'frozen_cell': {'layout': 'paved_road', 'maneuver': 'enter_road', 'control': 'other_vehicle'},
        'candidate_id': 'near_80', 'rate_hz': 20, 'frames': 600, 'duration_s': 30,
        'physical_completion': {'criterion': 'road_transition',
                                'motion_source': 'entry_history.jsonl',
                                'position_key': 'position_m', 'road_key': 'road_id',
                                'destination_road': 4, 'minimum_progress_m': 20,
                                'completion_goal_method': 'Original entry-road to highway departure-road transition with sampled path; engineering criterion only'},
        'required_atoms': [], 'source_packets': [], 'cameras': CAMERAS,
        'case': {'case_id': case}, 'supported_case_ids': [PREFIX + 'a', PREFIX + 'b'],
        'recording_description': {'channels': CHANNELS,
                                  'context_inputs': [{'name': 'controlled_access_authority',
                                                      'unit': 'structured',
                                                      'method': 'hash-bound public authority and access restriction review'}],
                                  'limitations': ['No legal hazard or reasonable-safety threshold is asserted',
                                                  'Controlled-access designation needs independent authority evidence']},
    }
    files = [{'path': name, 'content': (ROOT / name).read_text()} for name in FILES]
    files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'tests/test_selected.py', 'content': TEST}])
    proposal = {'case_id': case, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                'status': 'selected_native_cpu_draft_not_delivery_prepared',
                'recording_description': config['recording_description']}
    location = ROOT / 'cases' / ('condition_' + suffix) / 'construction.json'
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
    return case, location.relative_to(ROOT).as_posix(), sha256(location.read_bytes()).hexdigest()


if __name__ == '__main__':
    manifest_path = ROOT / 'execution-manifest.json'
    cases = []
    for suffix in ('a', 'b'):
        case, path, digest = make(suffix)
        cases.append({'case_id': case, 'kind': 'delivery', 'construction': path,
                      'construction_sha256': digest,
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Proposed ramp join and highway actor clearance need original motion and camera review'},
                      'candidates': [], 'delivery_readiness': 'incomplete',
                      'measurement_procedure': {'entrypoint': 'finalize.py',
                                                'output_schema': 'worker-c177626-saved-analysis-v1'},
                      'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                         'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3',
                'status': 'partial', 'cases': cases}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': [{key: item[key] for key in ('case_id', 'construction_sha256')}
                                for item in cases]}))
