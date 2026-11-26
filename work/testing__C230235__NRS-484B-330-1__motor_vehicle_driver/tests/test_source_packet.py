import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from flagger_zone import CASES, SOURCES
from source_packet import ASSIGNMENT, verify


def packet_fixture(folder, case):
    scene = {'cell_id': 'C230235', 'actor': 'motor_vehicle_driver',
             'qualifying_vehicle': True, 'highway': True,
             'driver_id': 'd1', 'vehicle_id': 'v1', 'flagger_id': 'f1',
             'designated': case.designated, 'marked_construction': case.marked_construction,
             'authorized': case.authorized,
             'signal': case.signal, 'response': case.response,
             'zone_rect_m': [0, 0, 50, 10], 'stop_line_xy': [10, 5],
             'flagger_xy': [10, 8], 'vehicle_route_xy': [[0, 5], [50, 5]],
             'signal_frame': 100, 'release_frame': 200}
    refs = {}
    for name in (*SOURCES, 'map_opendrive'):
        path = folder / (name + '.txt')
        path.write_text('synthetic ' + name + '\n')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        refs[name] = {'path': path.name, 'sha256': digest,
                      'observation': 'Synthetic software fixture for ' + name,
                      'review_status': 'synthetic'}
        scene['map_opendrive_sha256' if name == 'map_opendrive'
              else name + '_source_sha256'] = digest
    packet = {'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT + '__' + case.name,
              'source_kind': 'synthetic_fixture', 'review_status': 'synthetic',
              'scene': scene, 'source_refs': refs}
    path = folder / 'source-packet.json'
    path.write_text(json.dumps(packet, indent=2) + '\n')
    return path, packet


class PacketTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.runtime-work' / 'c230235-packet-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_exact_cases_verify_only_as_diagnostic(self):
        for case in CASES:
            with self.subTest(case=case.name):
                path, _ = packet_fixture(self.folder, case)
                self.assertEqual(verify(path, diagnostic_fixture=True)['source_kind'],
                                 'synthetic_fixture')
                with self.assertRaisesRegex(ValueError, 'provenance'):
                    verify(path)

    def test_missing_changed_and_unsourced_bytes_rejected(self):
        path, packet = packet_fixture(self.folder, CASES[0])
        (self.folder / 'flagger_authorization.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'bytes missing or changed'):
            verify(path, diagnostic_fixture=True)
        packet_fixture(self.folder, CASES[0])
        packet['source_refs']['signal_content']['observation'] = ''
        path.write_text(json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'observation missing'):
            verify(path, diagnostic_fixture=True)

    def test_traversal_and_scene_hash_mismatch_rejected(self):
        path, packet = packet_fixture(self.folder, CASES[0])
        packet['source_refs']['zone_designation']['path'] = '../external.txt'
        path.write_text(json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'adjacent'):
            verify(path, diagnostic_fixture=True)
        path, packet = packet_fixture(self.folder, CASES[0])
        packet['scene']['zone_designation_source_sha256'] = '0' * 64
        path.write_text(json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'scene/source hash'):
            verify(path, diagnostic_fixture=True)


if __name__ == '__main__':
    unittest.main()
