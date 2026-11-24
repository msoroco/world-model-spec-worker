"""Build two exact, unselected 30-second roundabout direction proposals."""
import hashlib
import json
import math
from pathlib import Path
from roundabout_direction import measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name
CAMERAS = [
    {'name': 'overview', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 95, 'location_xyz_m': [22, -32, 42], 'rotation_pyr_deg': [-55, 0, 90]},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 90, 'location_xyz_m': [22, -30, 8], 'rotation_pyr_deg': [-20, 0, 90]},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 90, 'location_xyz_m': [42, 0, 10], 'rotation_pyr_deg': [-25, 0, 180]},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 95, 'location_xyz_m': [1, 0, 1.5], 'rotation_pyr_deg': [0, 0, 0]},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def requested_track(direction):
    sign = 1 if direction == 'counterclockwise' else -1
    rows = []
    for frame in range(600):
        t = (frame + 1) / 20
        theta = -math.pi / 2 + sign * 4.0 * t / 16.75
        other_theta = -math.pi / 2 + 3.0 * t / 20.25 + math.pi / 2
        rows.append({'frame': frame, 'time_s': t,
                     'source_kind': 'authored_native_request',
                     'inside_roundabout': True,
                     'ego_xy_m': [22 + 16.75 * math.cos(theta), 16.75 * math.sin(theta)],
                     'ego_heading_deg': math.degrees(theta + sign * math.pi / 2),
                     'ego_requested_speed_mps': 4.0,
                     'other_vehicle_xy_m': [22 + 20.25 * math.cos(other_theta),
                                            20.25 * math.sin(other_theta)],
                     'other_requested_speed_mps': 3.0,
                     'original_native_observed': False})
    return rows


def main():
    runner = (SOURCE / 'runner.py').read_text()
    meter = (SOURCE / 'roundabout_direction.py').read_text()
    road = (SOURCE / 'roundabout-road.xodr').read_text()
    road_sha = sha(SOURCE / 'roundabout-road.xodr')
    cases = []
    for suffix, direction in (('probe_a', 'counterclockwise'),
                              ('probe_b', 'clockwise')):
        case_id = PREFIX + '__' + suffix
        rows = requested_track(direction)
        measured = measure(rows, 'authored_native_request')
        if measured['translational_direction'] != direction:
            raise ValueError('Authored route direction differs')
        track = ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                        for row in rows)
        config = {'case_id': case_id, 'law_id': 'LVMC-11-43-010-A',
                  'cell_id': 'C238396', 'actor': 'motor_vehicle_driver',
                  'roundabout_source': 'roundabout-road.xodr',
                  'roundabout_source_sha256': road_sha,
                  'road_source_provenance':
                    'work/training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver/right-exit-road.xodr',
                  'duration_s': 30, 'rate_hz': 20, 'frames': 600,
                  'requested_direction': direction,
                  'requested_ego_radius_m': 16.75,
                  'other_vehicle_radius_m': 20.25,
                  'observed_source_required': True,
                  'cameras': CAMERAS, 'physical_completion': False,
                  'legal_verdict': None}
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom roundabout_direction import check_config, read_and_measure\n\nclass ExactRoundabout(unittest.TestCase):\n def setUp(self): self.config=json.loads(Path('config.json').read_text())\n def test_exact(self):\n  self.assertEqual(check_config(self.config)['frames'],600)\n  meter=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(meter['translational_direction'],self.config['requested_direction'])\n  self.assertFalse(meter['physical_completion'])\n def test_negative(self):\n  for key,value in [('frames',599),('physical_completion',True),('observed_source_required',False)]:\n   bad=copy.deepcopy(self.config);bad[key]=value\n   with self.assertRaises(ValueError):check_config(bad)\n  lines=Path('requested-track.jsonl').read_text().splitlines()\n  Path('truncated-track.jsonl').write_text('\\n'.join(lines[:-1])+'\\n')\n  with self.assertRaises(ValueError):read_and_measure('truncated-track.jsonl','authored_native_request')\n'''
        construction = {'case_id': case_id, 'cell_id': 'C238396',
                        'law_id': 'LVMC-11-43-010-A',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'files': [{'path': 'runner.py', 'content': runner},
                                  {'path': 'roundabout_direction.py', 'content': meter},
                                  {'path': 'roundabout-road.xodr', 'content': road},
                                  {'path': 'requested-track.jsonl', 'content': track},
                                  {'path': 'config.json',
                                   'content': json.dumps(config, indent=2) + '\n'},
                                  {'path': 'tests/test_offline.py', 'content': test}],
                        'recording_description': {
                            'duration_s': 30, 'rate_hz': 20,
                            'source_cameras': [c['name'] for c in CAMERAS],
                            'measurement': 'signed radial cross product of consecutive saved ego xy positions',
                            'original_positions_required': True,
                            'physical_roundabout_and_jurisdiction_unverified': True,
                            'legal_verdict': None},
                        'status': 'draft_cpu_offline_only'}
        construction_path = BASE / 'draft-native' / suffix / 'construction.json'
        write(construction_path, construction)
        cases.append({'case_id': case_id,
                      'construction': str(construction_path.relative_to(BASE)),
                      'construction_sha256': sha(construction_path),
                      'candidates': [], 'candidate_risk': {
                          'status': 'physical',
                          'reason': 'Opposing travel and camera visibility on generated Native road require measurement and bounded fallback control.'}})
        write(SOURCE / ('request-meter-' + suffix + '.json'), measured)
    write(BASE / 'draft-native-manifest.json', {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': PREFIX, 'status': 'draft_not_selected',
        'cases': cases, 'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
