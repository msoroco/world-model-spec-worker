import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_construction import survey

spec = importlib.util.spec_from_file_location('departure_native_map', Path(__file__).resolve().parents[1] / 'native_map.py')
native_map = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_map)
CASE = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'


class FakeMap:
    name = 'unverified_survey_target'

    def __init__(self, opendrive='<OpenDRIVE/>\n'):
        self.opendrive = opendrive

    def to_opendrive(self):
        return self.opendrive


class FakeWorld:
    def __init__(self, opendrive='<OpenDRIVE/>\n'):
        self.map = FakeMap(opendrive)

    def get_map(self):
        return self.map


def write_survey(root):
    data = survey()
    data['source_sha256'] = hashlib.sha256(FakeMap().to_opendrive().encode()).hexdigest()
    path = root / 'survey.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


class NativeMapTests(unittest.TestCase):
    def test_loaded_map_identity_and_exact_construction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_survey(Path(tmp))
            result = native_map.verify_live_map(FakeWorld(), path, case_id=CASE)
            self.assertEqual(result['construction']['case_id'], CASE)
            self.assertFalse(result['physical_turn_verified'])
            self.assertFalse(result['public_highway_source_reviewed'])
            self.assertEqual(result['survey_packet_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_stale_map_and_name_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_survey(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE source hash differs'):
                native_map.verify_live_map(FakeWorld('<changed/>'), path, case_id=CASE)
            world = FakeWorld()
            world.map.name = 'other-map'
            with self.assertRaisesRegex(ValueError, 'map name differs'):
                native_map.verify_live_map(world, path, case_id=CASE)

    def test_foreign_case_and_missing_opposition_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_survey(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'exact assignment'):
                native_map.verify_live_map(FakeWorld(), path, case_id='foreign')
            data = json.loads(path.read_text())
            data['intersecting_roads'][0]['permitted_lanes'] = data['intersecting_roads'][0]['permitted_lanes'][:1]
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'opposed permitted lanes'):
                native_map.verify_live_map(FakeWorld(), path, case_id=CASE)


if __name__ == '__main__':
    unittest.main()
