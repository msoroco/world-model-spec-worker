"""Exercise original frame acquisition methods with a fake CARLA interface."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_frame import actor_state, capture_frames, capture_tick, verify_live_site
from tests.test_source_bound_scene import fixture


def point(x=0, y=0, z=0):
    return NS(x=x, y=y, z=z)


class Actor:
    def __init__(self, ident):
        self.id = ident
        self.type_id = "vehicle.protocol" if ident == 1 else "walker.protocol"
        self.bounding_box = NS(get_world_vertices=lambda transform:
                               [point(-1,-1), point(1,-1), point(1,1), point(-1,1)])
    def get_transform(self):
        return NS(location=point(), rotation=NS(yaw=90))
    def get_velocity(self):
        return point(0,1,0)
    def get_state(self):
        return "Red"


class World:
    def __init__(self, map_text="synthetic CPU site protocol: opendrive\n"):
        self.frame = 0
        self.map_text = map_text
    def get_map(self):
        return NS(to_opendrive=lambda: self.map_text)
    def tick(self):
        self.frame += 1
        return self.frame
    def get_snapshot(self):
        return NS(frame=self.frame, timestamp=NS(elapsed_seconds=self.frame / 20))


class NativeFrameTests(unittest.TestCase):
    def test_exact_world_and_body_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["signal"]["native_actor_id"] = "9"
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            world = World()
            scene = verify_live_site(world, path, "stopped_leftmost_clear", Actor(9))
            self.assertEqual(scene["selected_approach_lane_id"], "west")
            frames = list(capture_frames(world, Actor(1), Actor(9), [Actor(2)],
                                         [Actor(3)], count=2))
            self.assertEqual([item["frame"] for item in frames], [1, 2])
            self.assertEqual(len(frames[0]["ego"]["body_vertices_xyz_m"]), 4)
            self.assertEqual(frames[0]["signal_state"], "Red")
            self.assertEqual(frames[0]["pedestrians"][0]["actor_id"], "2")
            self.assertEqual(frames[0]["origin"], "native_world_snapshot")

    def test_changed_map_signal_frame_and_actor_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["signal"]["native_actor_id"] = "9"
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "live OpenDRIVE differs"):
                verify_live_site(World("changed"), path, "stopped_leftmost_clear", Actor(9))
            with self.assertRaisesRegex(ValueError, "live signal actor differs"):
                verify_live_site(World(), path, "stopped_leftmost_clear", Actor(8))
            world = World()
            with self.assertRaisesRegex(ValueError, "snapshot frame differs"):
                capture_tick(world, Actor(1), Actor(9), [], [], expected_frame=1)
            with self.assertRaisesRegex(ValueError, "duplicate Native participant"):
                capture_tick(world, Actor(1), Actor(9), [Actor(1)], [], expected_frame=0)


if __name__ == "__main__":
    unittest.main()
