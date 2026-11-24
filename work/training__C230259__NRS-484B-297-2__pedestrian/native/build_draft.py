"""Bind two unselected walking comparisons to exact inline construction hashes."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CASE = 'training__C230259__NRS-484B-297-2__pedestrian__selected_81846e7f__condition_'
CAMERAS = [
    {'name': 'overview', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 95,
     'location_xyz_m': [-7, 0, 5], 'rotation_pyr_deg': [-20, 0, 0]},
    {'name': 'ego_front', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 85,
     'location_xyz_m': [3, 0, 2], 'rotation_pyr_deg': [-4, 0, 0]},
    {'name': 'curb_side', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 90,
     'location_xyz_m': [-4, 2, 1.3], 'rotation_pyr_deg': [0, -25, 0]},
    {'name': 'traffic_rear', 'width': 1280, 'height': 720, 'fps': 20, 'fov_deg': 95,
     'location_xyz_m': [-7, 0, 2], 'rotation_pyr_deg': [0, 180, 0]},
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    source = Path(__file__).resolve().parent
    runner = (source / 'runner.py').read_text()
    meter = (source / 'walking_side.py').read_text()
    cases = []
    for condition in ('a', 'b'):
        case_id = CASE + condition
        config = {'case_id': case_id, 'selected_case_ids': [CASE + 'a', CASE + 'b'],
                  'law_id': 'NRS-484B-297-2', 'cell_id': 'C230259', 'actor': 'pedestrian',
                  'case': 'condition_' + condition, 'condition': condition, 'rate_hz': 20,
                  'duration_s': 30, 'frames': 600, 'source_packet_required': True,
                  'source_packets': [], 'required_atoms': ['kin.position', 'kin.speed'],
                  'cameras': CAMERAS, 'physical_completion': False, 'legal_verdict': None}
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom runner import check, _packet\n\nclass ExactDraft(unittest.TestCase):\n def setUp(self): self.config=json.loads(Path('config.json').read_text())\n def test_contract(self):\n  receipt=check(self.config)\n  self.assertEqual(receipt['frames'],600)\n  self.assertFalse(receipt['physical_completion'])\n  self.assertFalse(receipt['carla_contacted'])\n def test_negative(self):\n  for key,value in [('frames',599),('actor','driver'),('physical_completion',True),('source_packet_required',False)]:\n   bad=copy.deepcopy(self.config);bad[key]=value\n   with self.assertRaises(ValueError):check(bad)\n def test_no_unsourced_native(self):\n  with self.assertRaises(FileNotFoundError):_packet('missing-original-source.json',self.config)\n'''
        construction = {'case_id': case_id, 'cell_id': 'C230259', 'law_id': 'NRS-484B-297-2',
                        'actor': 'pedestrian', 'entrypoint': 'runner.py',
                        'files': [{'path': 'runner.py', 'content': runner},
                                  {'path': 'walking_side.py', 'content': meter},
                                  {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                                  {'path': 'tests/test_offline.py', 'content': test}],
                        'recording_description': {'duration_s': 30, 'rate_hz': 20,
                                                  'source_cameras': [x['name'] for x in CAMERAS],
                                                  'highway_and_sidewalk_source_required': True,
                                                  'subsection_6_source_required': True,
                                                  'legal_verdict': None},
                        'status': 'draft_cpu_offline_only'}
        path = BASE / 'draft-native' / condition / 'construction.json'
        write(path, construction)
        cases.append({'case_id': case_id, 'construction': str(path.relative_to(BASE)),
                      'construction_sha256': digest(path), 'candidates': [],
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Native highway boundary, sidewalk absence, pedestrian route and camera visibility require source review; fallback not yet built.'}})
    write(BASE / 'draft-native-manifest.json',
          {'format': 'worker-unselected-draft-construction-manifest-v1',
           'assignment_id': BASE.name, 'status': 'draft_not_selected', 'cases': cases,
           'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
