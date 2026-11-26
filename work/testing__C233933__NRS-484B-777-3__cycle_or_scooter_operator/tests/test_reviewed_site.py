import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from abreast import CASES, SOURCES
from original_runner import reviewed_site
from package_spec import AID, CAMERA_NAMES

class ReviewedSiteTests(unittest.TestCase):
    def packet(self, folder):
        case = CASES[0]
        scene = {'cell_id': 'C233933', 'actor': 'cycle_or_scooter_operator',
                 'highway': True, 'sidewalk_absent': True, 'exclusive': False,
                 'roadway': True, 'rider_ids': ['ego', 'control', 'companion'],
                 'ego_id': 'ego', 'control_id': 'control',
                 'vehicle_type': 'human_powered_bicycle', 'moped': False,
                 'roadway_rect_m': [0, 0, 60, 10],
                 'shoulder_rect_m': [0, 9, 60, 10],
                 'occupied_surface_rect_m': [0, 0, 60, 8],
                 'rider_routes_xy': [[[0, 1 + i], [60, 1 + i]] for i in range(3)]}
        refs = []
        for role in ('map', *SOURCES):
            name = role + '.txt'
            path = folder / name
            path.write_text('reviewed-' + role + '\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            refs.append({'role': role, 'path': name, 'sha256': digest})
            if role != 'map':
                scene[role + '_source_sha256'] = digest
        packet = {'reviewed_original_native_site': True,
                  'source_kind': 'original_native_map_geometry',
                  'assignment_id': AID, 'case_id': AID + '__' + case.name,
                  'duration_frames': 900, 'rate_hz': 20, 'cameras': list(CAMERA_NAMES),
                  'map_name': 'reviewed-map', 'map_sha256': refs[0]['sha256'],
                  'source_refs': refs, 'scene': scene,
                  'bicycle_blueprint_id': 'vehicle.bh.crossbike'}
        source = folder / 'site.json'
        source.write_text(json.dumps(packet) + '\n')
        return source, packet

    def test_complete_source_bindings(self):
        root = ROOT / '.runtime-work' / 'c233933-owner-nov26'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            path, packet = self.packet(Path(temp))
            reviewed, case = reviewed_site(path, packet['case_id'])
            self.assertEqual(case.name, CASES[0].name)
            self.assertEqual(reviewed['scene']['rider_ids'], ['ego', 'control', 'companion'])
            packet['scene']['bicycle_classification_source_sha256'] = '0' * 64
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'rider context source binding differs'):
                reviewed_site(path, packet['case_id'])

    def test_missing_source_file_rejected(self):
        root = ROOT / '.runtime-work' / 'c233933-owner-nov26'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            path, packet = self.packet(Path(temp))
            (Path(temp) / 'exclusive_use_designation.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'reviewed rider source changed'):
                reviewed_site(path, packet['case_id'])

if __name__ == '__main__':
    unittest.main()
