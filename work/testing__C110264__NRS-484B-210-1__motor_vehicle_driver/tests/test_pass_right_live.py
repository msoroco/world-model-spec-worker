"""Fake-world checks for same-attempt source map binding."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_live import bind_live_route
from test_pass_right_route import map_packet


class FakeMap:
    name = 'TownSource'

    def __init__(self, opendrive='original-opendrive-text'):
        self.opendrive = opendrive

    def to_opendrive(self):
        return self.opendrive


class FakeWorld:
    def __init__(self, loaded_map=None):
        self.loaded_map = loaded_map or FakeMap()

    def get_map(self):
        return self.loaded_map


def packet_file(root, **changes):
    packet = map_packet()
    packet.update(map_name='TownSource', source_opendrive_sha256=hashlib.sha256(
        b'original-opendrive-text').hexdigest())
    packet.update(changes)
    path = root / 'source-map.json'
    path.write_text(json.dumps(packet))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class TestLiveMapBinding(unittest.TestCase):
    def test_all_exact_routes_bind_to_same_loaded_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, sha = packet_file(Path(tmp))
            rows = [bind_live_route(FakeWorld(), path, sha, v)
                    for v in ('left_signal', 'left_turn', 'neither')]
            self.assertEqual(len({r['loaded_opendrive_sha256'] for r in rows}), 1)
            self.assertEqual([r['route_request']['target_left_signal_request'] for r in rows],
                             [True, False, False])
            self.assertFalse(any(r['physical_acceptance_claimed'] for r in rows))

    def test_rejects_stale_map_and_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, sha = packet_file(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'loaded map identity'):
                other = type('OtherMap', (FakeMap,), {'name': 'TownOther'})()
                bind_live_route(FakeWorld(other), path, sha, 'left_turn')
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE sha256 differs'):
                bind_live_route(FakeWorld(FakeMap('modified-opendrive')), path, sha, 'left_turn')
            path.write_text(path.read_text().replace('TownSource', 'TownOther'))
            with self.assertRaisesRegex(ValueError, 'map packet sha256 mismatch'):
                bind_live_route(FakeWorld(), path, sha, 'left_turn')

    def test_requires_original_source_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, sha = packet_file(root, source_opendrive_sha256='')
            with self.assertRaisesRegex(ValueError, 'source OpenDRIVE sha256 required'):
                bind_live_route(FakeWorld(), path, sha, 'neither')
            path, sha = packet_file(root, map_name='')
            with self.assertRaisesRegex(ValueError, 'source map name required'):
                bind_live_route(FakeWorld(), path, sha, 'neither')


if __name__ == '__main__':
    unittest.main()
