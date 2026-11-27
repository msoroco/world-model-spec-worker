import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

folder = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reviewed_site_c147331', folder / 'reviewed_site.py')
reviewed = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reviewed
spec.loader.exec_module(reviewed)


class Tests(unittest.TestCase):
    def test_separate_authority_and_native_source_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            refs = []
            site = {}
            for role, field in reviewed.ROLES.items():
                path = root / (role + '.json')
                path.write_text(json.dumps({'role': role, 'reviewed': True}) + '\n')
                digest = sha256(path.read_bytes()).hexdigest()
                refs.append({'role': role, 'path': path.name, 'sha256': digest})
                site[field] = digest
            site['source_refs'] = refs
            site['assignment_id'] = 'testing__C3997__NRS-484B-587-2b__motor_vehicle_driver'
            site['native_spawn'] = {'blueprint_id': 'vehicle.test', 'pose_xyz_ypr': [0, 0, 0, 0, 0, 0]}
            site['lane_change_control'] = 'solid_white_line'
            path = root / 'site.json'
            path.write_text(json.dumps(site) + '\n')
            self.assertEqual(reviewed.load(path)['map_sha256'], site['map_sha256'])
            (root / 'controlled_access_determination.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash changed: controlled_access_determination'):
                reviewed.load(path)
            (root / 'controlled_access_determination.json').write_text(json.dumps({'role': 'controlled_access_determination', 'reviewed': True}) + '\n')
            site['source_refs'].pop()
            path.write_text(json.dumps(site) + '\n')
            with self.assertRaisesRegex(ValueError, 'role missing'):
                reviewed.load(path)
