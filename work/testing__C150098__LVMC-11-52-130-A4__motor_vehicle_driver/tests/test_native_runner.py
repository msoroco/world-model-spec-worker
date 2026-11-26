"""Source-shaped Native lifecycle tests with an in-memory adapter."""
import unittest
from pathlib import Path

from test_hydrant import Adapter
from test_native_packet import PacketTest
from native_runner import CAMERAS, FRAMES, capture_original
from saved_audit import audit


class Pipeline:
    def __init__(self, client, actor, output, case_id, required_observations):
        self.closed = False

    def capture(self, frame, elapsed):
        return {'frame': frame, 'time_s': elapsed}

    def close(self, confirmed):
        self.closed = True


class NativeAdapter(Adapter):
    def __init__(self, site):
        super().__init__()
        self.site = site
        self.index = 0
        self.restored = False
        self.bad_cameras = False

    def provenance(self):
        return 'original_native'

    def verify_loaded_map(self, digest):
        return digest == self.site['map_sha256']

    def read_hydrant(self, hydrant):
        return {'identity_sha256': self.site['hydrant_identity_sha256'],
                'geometry_sha256': self.site['hydrant_geometry_sha256'],
                'physically_present': True}

    def vehicle_body_length_m(self):
        return 4.0

    def pipeline_client(self):
        return object()

    def start_cameras(self, output, cameras):
        assert tuple(c['name'] for c in cameras) == CAMERAS
        self.output = Path(output)

    def advance_case(self, built, case, index, frames):
        assert frames == FRAMES
        self.index = index

    def tick_world(self):
        return 1000 + self.index, 50 + self.index / 20

    def camera_frame_ids(self, frame):
        if self.bad_cameras:
            return {name: frame + 1 for name in CAMERAS}
        return {name: frame for name in CAMERAS}

    def sample_body_hydrant(self, built, frame):
        west, east = built['target_body_interval_m']
        return {'actor_id': 11, 'hydrant_actor_id': 22,
                'hydrant_physically_present': True, 'body_source_sha256': 'body-fixture',
                'body_west_x_m': west, 'body_east_x_m': east,
                'activity_observation': 'parked', 'exception_kind': 'none'}

    def finish_cameras(self):
        paths = {}
        for name in CAMERAS:
            path = self.output / (name + '.mkv')
            path.write_bytes(b'synthetic fixture only')
            paths[name] = path
        return paths

    def abort_cameras(self):
        self.calls.append('abort_cameras')

    def restore_world(self):
        self.restored = True
        return True


class NativeRunnerTest(unittest.TestCase):
    setUp = PacketTest.setUp
    save = PacketTest.save

    def test_900_frame_source_join_and_saved_input(self):
        adapter = NativeAdapter(self.payload['site'])
        output = self.root / 'original-attempt'
        receipt = capture_original(adapter, self.packet, self.case_id, output,
                                   pipeline_factory=Pipeline)
        self.assertEqual(receipt['frames'], 900)
        self.assertFalse(receipt['physical_visibility_verified'])
        self.assertEqual(len((output / 'original-hydrant-history.jsonl').read_text().splitlines()), 900)
        saved = audit(output, 'upstream_inside')
        self.assertEqual(saved['frame_count'], 900)
        self.assertAlmostEqual(saved['measurement']['minimum_longitudinal_gap_m'], 4.422)
        self.assertTrue(adapter.restored)
        self.assertEqual(len(adapter.destroyed), 2)

    def test_bad_camera_join_cleans_up(self):
        adapter = NativeAdapter(self.payload['site'])
        adapter.bad_cameras = True
        with self.assertRaisesRegex(ValueError, 'four cameras not joined'):
            capture_original(adapter, self.packet, self.case_id, self.root / 'bad-attempt',
                             pipeline_factory=Pipeline)
        self.assertTrue(adapter.restored)
        self.assertEqual(len(adapter.destroyed), 2)
        self.assertIn('abort_cameras', adapter.calls)


if __name__ == '__main__':
    unittest.main()
