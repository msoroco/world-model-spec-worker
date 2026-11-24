"""Build two no-marked-reference, 30-second blind-intersection proposals."""
import hashlib
import json
from pathlib import Path
from sight_stop import check_config, measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name
CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'fps': 20,
     'fov_deg': 95, 'location_xyz_m': [0, -35, 35], 'rotation_pyr_deg': [-55, 0, 90]},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 90, 'location_xyz_m': [0, -35, 8], 'rotation_pyr_deg': [-15, 0, 90]},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 90, 'location_xyz_m': [-10, -10, 10], 'rotation_pyr_deg': [-20, 0, 45]},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 95, 'location_xyz_m': [1, 0, 1.5], 'rotation_pyr_deg': [0, 0, 0]},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def track(stop):
    rows = []
    for frame in range(600):
        t = (frame + 1) / 20
        travel_time = min(t, 11.25) if stop and t < 14.25 else t - 3 if stop else t
        y = -70 + 4 * travel_time
        speed = 0 if stop and 11.25 <= t < 14.25 else 4
        rows.append({'frame': frame, 'time_s': t,
                     'source_kind': 'authored_native_request',
                     'ego_center_xy_m': [1.75, y], 'ego_speed_mps': speed,
                     'other_vehicle_xy_m': [-30 + 3 * t, 1.75],
                     'other_vehicle_requested_speed_mps': 3,
                     'original_native_observed': False})
    return rows


def main():
    road = (SOURCE / 'road.xodr').read_text()
    runner = (SOURCE / 'runner.py').read_text()
    meter = (SOURCE / 'sight_stop.py').read_text()
    cases = []
    for suffix, stop in (('probe_a', True), ('probe_b', False)):
        case_id = PREFIX + '__' + suffix
        rows = track(stop)
        request = ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                          for row in rows)
        report = measure(rows, 'authored_native_request')
        if report['diagnostic_full_halt_span'] != stop:
            raise ValueError('Requested stop contrast differs')
        config = {'case_id': case_id, 'law_id': 'NRS-484A-450-2',
                  'cell_id': 'C24805', 'actor': 'motor_vehicle_driver',
                  'duration_s': 30, 'rate_hz': 20, 'frames': 600,
                  'requested_pre_entry_stop': stop,
                  'road_source_sha256': sha(SOURCE / 'road.xodr'),
                  'road_source_provenance':
                    'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver/native/road.xodr; near-side marked crosswalk object removed for this branch',
                  'unmarked_crosswalk_source_audit_required': True,
                  'sight_source_required': True,
                  'cameras': CAMERAS, 'physical_completion': False,
                  'legal_verdict': None}
        check_config(config, road)
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom sight_stop import check_config, read_and_measure\n\nclass ExactRequest(unittest.TestCase):\n def setUp(self): self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  result=check_config(self.config,Path('road.xodr').read_text())\n  self.assertEqual(result['frames'],600)\n  self.assertFalse(result['unmarked_crosswalk_absence_verified'])\n def test_motion(self):\n  result=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(result['diagnostic_full_halt_span'],self.config['requested_pre_entry_stop'])\n  self.assertFalse(result['view_point_nearest_intersecting_highway_verified'])\n def test_negative(self):\n  for key,value in [('frames',599),('physical_completion',True),('sight_source_required',False)]:\n   config=copy.deepcopy(self.config);config[key]=value\n   with self.assertRaises(ValueError):check_config(config,Path('road.xodr').read_text())\n  lines=Path('requested-track.jsonl').read_text().splitlines()\n  Path('truncated-track.jsonl').write_text('\\n'.join(lines[:-1])+'\\n')\n  with self.assertRaises(ValueError):read_and_measure('truncated-track.jsonl','authored_native_request')\n'''
        construction = {'case_id': case_id, 'law_id': 'NRS-484A-450-2',
                        'cell_id': 'C24805', 'actor': 'motor_vehicle_driver',
                        'entrypoint': 'runner.py',
                        'files': [{'path': 'runner.py', 'content': runner},
                                  {'path': 'sight_stop.py', 'content': meter},
                                  {'path': 'road.xodr', 'content': road},
                                  {'path': 'requested-track.jsonl', 'content': request},
                                  {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                                  {'path': 'tests/test_offline.py', 'content': test}],
                        'recording_description': {
                            'duration_s': 30, 'rate_hz': 20,
                            'source_cameras': [c['name'] for c in CAMERAS],
                            'authored_marked_crosswalk_absent': True,
                            'authored_marked_stop_line_absent': True,
                            'unmarked_crosswalk_and_nearest_visible_point_unverified': True,
                            'legal_verdict': None},
                        'status': 'draft_cpu_offline_only'}
        path = BASE / 'draft-native' / suffix / 'construction.json'
        write(path, construction)
        cases.append({'case_id': case_id,
                      'construction': str(path.relative_to(BASE)),
                      'construction_sha256': sha(path), 'candidates': [],
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Occluded Native sight, unmarked crosswalk absence, stop-sign visibility and actual stop location require source measurements.'}})
        write(SOURCE / ('request-meter-' + suffix + '.json'), report)
    write(BASE / 'draft-native-manifest.json', {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': PREFIX, 'status': 'draft_not_selected',
        'cases': cases, 'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
