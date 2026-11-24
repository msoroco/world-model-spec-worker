"""Build two source-bound, unselected Native capture proposals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
TEST = '''import copy
import json
import unittest
from pathlib import Path
from runner import check, FRAMES, RATE
from controller import control


class DraftContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_source_capture(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(FRAMES, 600)
        self.assertEqual(RATE, 20)
        self.assertFalse(result['pupils_aboard_observed'])
        self.assertFalse(result['legal_verdict_claimed'])

    def test_reject_camera_or_pupil_claim(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['pupils_aboard_observed'] = True
        with self.assertRaises(ValueError):
            check(bad)

    def test_speed_feedback_is_request_only(self):
        suffix = self.config['case_id'].rsplit('__', 1)[-1]
        request = control(suffix, [0, 0, 0])
        self.assertEqual(request['measurement_source'], 'post_tick_original_velocity')
        self.assertGreater(request['requested_speed_mps'], 0)
        self.assertIsNone(self.config['legal_verdict'])

    def test_reject_short_capture(self):
        bad = copy.deepcopy(self.config)
        bad['duration_s'] = 29
        with self.assertRaises(ValueError):
            check(bad)
'''


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runner = (NATIVE / 'draft_runner.py').read_text()
    controller = (NATIVE / 'controller.py').read_text()
    cases = []
    for suffix, speed in [('probe_a', 52), ('probe_b', 58)]:
        case = ROOT.name + '__' + suffix
        config = {
            'case_id': case, 'selected_case_id': None,
            'law_id': 'NRS-484B-360-1', 'cell_id': 'C230241',
            'actor': 'school_bus_driver', 'cell_control': 'ice_cream_truck',
            'duration_s': 30, 'rate_hz': 20, 'requested_speed_mph': speed,
            'spawn_point_index': 0, 'ice_cream_spawn_offset': 3,
            'school_bus_blueprint_confirmed': False,
            'pupils_aboard_observed': False, 'legal_verdict': None,
            'required_atoms': ['kin.position', 'kin.speed'],
            'cameras': [
                {'name': 'forward', 'width': 1920, 'height': 1080,
                 'fov_deg': 90, 'pose': [2.2, 0, 2.5, 0, 0, 0]},
                {'name': 'rear', 'width': 1920, 'height': 1080,
                 'fov_deg': 90, 'pose': [-2.2, 0, 2.5, 0, 180, 0]},
                {'name': 'left', 'width': 1920, 'height': 1080,
                 'fov_deg': 90, 'pose': [0, -1.1, 2.5, 0, -90, 0]},
                {'name': 'right', 'width': 1920, 'height': 1080,
                 'fov_deg': 90, 'pose': [0, 1.1, 2.5, 0, 90, 0]},
            ],
        }
        construction = {
            'actor': config['actor'], 'case_id': case, 'cell_id': config['cell_id'],
            'law_id': config['law_id'], 'entrypoint': 'runner.py',
            'status': 'draft_unselected_cpu_offline_only',
            'files': [
                {'path': 'runner.py', 'content': runner},
                {'path': 'controller.py', 'content': controller},
                {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                {'path': 'tests/test_offline.py', 'content': TEST},
            ],
            'measurement_plan': 'Retain 600 original post-tick bus velocity samples, '
                                'joined frame IDs and four 1920x1080 camera streams. '
                                'Independent reviewer must establish actual school-bus '
                                'class, pupils aboard and trip purpose from originals.',
            'mechanisms': ['20 Hz synchronous source capture',
                           'source velocity feedback control',
                           'exact asset resolution or explicit failure'],
            'recording_description': {
                'channels': [{'name': 'bus_speed_mph', 'unit': 'mph',
                              'sampling_rate_hz': 20,
                              'method': 'norm of original post-tick velocity divided by 0.44704',
                              'time_window': '600 original frames'}],
                'limitations': ['Pupil occupancy and school trip purpose are not '
                                'established by a CARLA actor or synthetic fixture.']},
            'termination_rules': ['600 synchronized frames or explicit failure'],
            'static_checks': ['both exact identities', 'four source cameras',
                              '600-frame duration', 'no invented school-trip verdict'],
        }
        construction_path = ROOT / 'draft-primary' / suffix / 'primary' / 'construction.json'
        write(construction_path, construction)
        cases.append({'case_id': case, 'kind': 'draft_not_selected',
                      'construction': str(construction_path.relative_to(ROOT)),
                      'construction_sha256': sha(construction_path),
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Exact school-bus/ice-cream assets and pupil context '
                                    'require original Native and independent source review.'}})
    manifest_path = ROOT / 'draft-primary-manifest.json'
    write(manifest_path, {'format': 'worker-unselected-draft-construction-manifest-v1',
                          'assignment_id': ROOT.name, 'status': 'draft_cpu_offline_only',
                          'cases': cases})
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'constructions': {c['case_id']: c['construction_sha256'] for c in cases}}))


if __name__ == '__main__':
    main()
