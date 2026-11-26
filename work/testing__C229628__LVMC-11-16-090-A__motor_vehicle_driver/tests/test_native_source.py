"""Reject missing or altered independent Native site source packets."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from contest_aid import CASES, SOURCE_FIELDS
from native_source import AID, CAMERAS, read_site


class NativeSourceTests(unittest.TestCase):
    def setUp(self):
        self.base = Path('.runtime-work') / ('c229628-source-test-' + uuid4().hex)
        self.base.mkdir(parents=True)
        self.case = CASES[0]
        self.case_id = AID + '__' + self.case.name
        self.scene = {'cell_id': 'C229628', 'actor': 'motor_vehicle_driver',
                      'municipal_jurisdiction': True, 'highway': True,
                      'candidate_contest': True, 'cue': True,
                      'ego_person_id': 'p1', 'other_person_id': 'p2',
                      'ego_vehicle_id': 'v1', 'other_vehicle_id': 'v2',
                      'ego_route_xy': [[0., 0.], [50., 0.]],
                      'other_route_xy': [[0., 3.], [50., 3.]],
                      'lane_marking_xy': [[0., 1.5], [50., 1.5]],
                      'cue_frame': 100, 'other_start_frame': 120}
        refs = []
        for role in (*SOURCE_FIELDS, 'map'):
            name = role + '.txt'
            path = self.base / name
            path.write_text(role + ': reviewed source\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            refs.append({'role': role, 'path': name, 'sha256': digest})
            self.scene[role + '_source_sha256'] = digest
        self.site = {'assignment_id': AID, 'case_id': self.case_id,
                     'source_kind': 'reviewed_original_native_site',
                     'map_name': 'Town01', 'map_sha256': refs[-1]['sha256'],
                     'rate_hz': 20, 'duration_frames': 900,
                     'cameras': list(CAMERAS), 'source_refs': refs, 'scene': self.scene}
        self.site_path = self.base / 'site.json'
        self.site_path.write_text(json.dumps(self.site) + '\n')

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_exact_source_loaded_and_tamper_rejected(self):
        packet, scene, case = read_site(self.site_path, self.case_id)
        self.assertEqual(scene['ego_person_id'], 'p1')
        self.assertEqual(case.name, self.case.name)
        self.assertEqual(len(packet['site_sha256']), 64)
        (self.base / 'ego_identity.txt').write_text('replaced\n')
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            read_site(self.site_path, self.case_id)

    def test_missing_source_and_case_rejected(self):
        self.site['source_refs'].pop()
        self.site_path.write_text(json.dumps(self.site) + '\n')
        with self.assertRaisesRegex(ValueError, 'independent source missing'):
            read_site(self.site_path, self.case_id)
        with self.assertRaisesRegex(ValueError, 'exact reviewed site'):
            read_site(self.site_path, AID + '__other')


if __name__ == '__main__':
    unittest.main()
