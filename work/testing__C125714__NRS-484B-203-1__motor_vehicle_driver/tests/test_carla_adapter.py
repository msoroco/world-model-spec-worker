"""Original Native actor/body/camera readback joins for opposing passing."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
from carla_adapter import CarlaOpposingAdapter
from native_history import capture
from test_native_history import vertices
from test_opposing_pass import site


def vec(point):
    return SimpleNamespace(x=point[0], y=point[1], z=point[2])


class Actor:
    def __init__(self, actor_id, station, lateral, speed):
        self.id, self.station, self.lateral, self.speed = actor_id, station, lateral, speed
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda _: [vec(v) for v in
                                               vertices(self.station, self.lateral)])

    def get_transform(self):
        return object()

    def get_velocity(self):
        return vec((self.speed, 0, 0))


class World:
    frame = 100
    name = 'ReviewedTown'

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=.05)

    def get_map(self):
        return SimpleNamespace(name=self.name)

    def tick(self):
        self.frame += 1
        if hasattr(self, 'ego'):
            self.ego.station += 1
            self.other.station -= 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=20+(self.frame-101)/20))


class CarlaOpposingAdapterTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        packet = site()
        packet['native_road_frame'] = {'source_id': 'reviewed-axis',
                                       'origin_xyz_m': [0, 0, 0], 'forward_xy': [1, 0]}
        packet['paved_boundary_source'] = 'reviewed-edges'
        self.map_path = self.root / 'map.json'
        self.map_path.write_text(json.dumps(packet)+'\n')
        self.digest = hashlib.sha256(self.map_path.read_bytes()).hexdigest()
        self.world = World()
        self.ego = Actor(1, -2, -1.7, 6)
        self.other = Actor(2, 2, 1.7, -6)
        self.world.ego, self.world.other = self.ego, self.other
        self.readers = {name: lambda frame: {'frame': frame, 'png_bytes': b'png'}
                        for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}

    def adapter(self):
        return CarlaOpposingAdapter(self.world, self.ego, self.other, self.readers,
                                    self.map_path, native_map_name='ReviewedTown',
                                    source_ref='original-reviewed-site')

    def test_original_tick_feeds_source_bound_history(self):
        adapter = self.adapter()
        sample = adapter.tick()
        self.assertEqual(sample['native_frame'], 101)
        self.assertEqual(len(sample['ego']['vertices_world_xyz_m']), 8)
        self.assertEqual(set(sample['cameras']), set(self.readers))
        self.assertEqual(adapter.source_attestation()['map_sha256'], self.digest)
        receipt = capture(adapter, self.map_path, self.digest, 'right_half',
                          self.root / 'trace.json', frames=3, diagnostic_fixture=True)
        self.assertEqual(receipt['frame_count'], 3)

    def test_rejects_source_world_camera_and_actor_drift(self):
        self.world.name = 'OtherTown'
        with self.assertRaisesRegex(ValueError, 'map name differs'):
            self.adapter()
        self.world.name = 'ReviewedTown'
        adapter = self.adapter()
        self.map_path.write_text(self.map_path.read_text()+' ')
        with self.assertRaisesRegex(ValueError, 'map packet changed'):
            adapter.tick()
        self.map_path.write_text(self.map_path.read_text()[:-1])
        self.readers['approach'] = lambda frame: {'frame': frame+1, 'png_bytes': b'png'}
        with self.assertRaisesRegex(ValueError, 'camera frame'):
            self.adapter().tick()
        self.other.id = self.ego.id
        with self.assertRaisesRegex(ValueError, 'distinct original actors'):
            self.adapter()


if __name__ == '__main__':
    unittest.main()
