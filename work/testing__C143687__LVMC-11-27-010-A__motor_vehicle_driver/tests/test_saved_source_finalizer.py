import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_source_packet import fixture
from test_trail_capture import World, Vehicle, capture, CASES


MODULE = Path(__file__).resolve().parents[1] / 'saved_source_finalizer.py'
spec = importlib.util.spec_from_file_location('trail_saved_source_finalizer', MODULE)
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)
SCRATCH = MODULE.parents[2] / '.runtime-work' / 'c143687-finalizer-tests'
PREFIX = 'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver__'
CASE_ID = PREFIX + 'all_prerequisites'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_attempt(root, case=CASES[0]):
    case_id = PREFIX + case.name
    site, packet_path, packet = fixture(root, case)
    world = World()
    map_path = root / 'map.txt'
    map_path.write_text(world.get_map().to_opendrive())
    site['map_sha256'] = sha(map_path)
    site['case_id'] = case_id
    site['provenance_kind'] = 'diagnostic_fixture'
    packet['sources']['map']['sha256'] = site['map_sha256']
    packet_path.write_text(json.dumps(packet))
    site_path = root / 'site.json'
    site_path.write_text(json.dumps(site))
    history = root / 'original-history.jsonl'
    capture(world, Vehicle(world), 'driver-1', lambda snapshot, sign: snapshot.frame == 112,
            site, case, packet_path, history, 'camera-plan')
    packets = root / 'original-history-packets.jsonl'
    cameras = {}
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        path = root / (name + '.mkv')
        path.write_bytes(('diagnostic-' + name).encode())
        cameras[name] = {'path': path.name, 'sha256': sha(path)}
    acquisition = {
        'case_id': case_id, 'cell_id': 'C143687', 'frame_count': 900, 'fps': 20,
        'provenance_kind': 'diagnostic_fixture', 'diagnostic_fixture': True,
        'site': {'path': site_path.name, 'sha256': sha(site_path)},
        'source_packet': {'path': packet_path.name, 'sha256': sha(packet_path)},
        'packet_stream': {'path': packets.name, 'sha256': sha(packets)},
        'history': {'path': history.name, 'sha256': sha(history)},
        'camera_media': cameras,
    }
    path = root / 'acquisition.json'
    path.write_text(json.dumps(acquisition))
    return path, acquisition


class SavedSourceFinalizerTests(unittest.TestCase):
    def test_all_six_exact_case_saved_joins(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            for case in CASES:
                with self.subTest(case=case.name):
                    root = Path(tmp) / case.name
                    root.mkdir()
                    make_attempt(root, case)
                    report = finalizer.finalize(root, PREFIX + case.name)
                    self.assertEqual(report['case_id'], PREFIX + case.name)
                    self.assertEqual(report['measurements']['emergency_use']['value'], case.emergency_use)
                    self.assertEqual(report['measurements']['maintenance_use']['value'], case.maintenance_use)

    def test_measures_all_source_conditions_without_legal_or_pixel_claim(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            root = Path(tmp)
            make_attempt(root)
            report = finalizer.finalize(root, CASE_ID)
            self.assertTrue(report['measurements']['trail_corridor_entry']['value'])
            self.assertTrue(report['measurements']['official_plan_designation']['value'])
            self.assertEqual(report['frame_count'], 900)
            self.assertFalse(report['full_video_decode'])
            self.assertFalse(report['physical_completion'])
            self.assertIsNone(report['legal_judgment'])

    def test_rejects_changed_source_and_resealed_false_packet(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            root = Path(tmp)
            acquisition_path, acquisition = make_attempt(root)
            (root / 'map.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'map source hash mismatch'):
                finalizer.finalize(root, CASE_ID)
            world_map = World().get_map().to_opendrive()
            (root / 'map.txt').write_text(world_map)
            packets = root / acquisition['packet_stream']['path']
            raw = packets.read_bytes().replace(b'"location_xy": [-2.0, 2.0]',
                                               b'"location_xy": [2.0, 2.0]', 1)
            packets.write_bytes(raw)
            acquisition['packet_stream']['sha256'] = sha(packets)
            acquisition_path.write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'history/packet hash join mismatch'):
                finalizer.finalize(root, CASE_ID)


if __name__ == '__main__':
    unittest.main()
