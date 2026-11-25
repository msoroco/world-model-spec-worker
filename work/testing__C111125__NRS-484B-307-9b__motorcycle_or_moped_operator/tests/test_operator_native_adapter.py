"""CPU tests for the reviewed-source CARLA session boundary."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import operator_native_adapter as adapter
from test_native_session import CASE, make_site


class FakeWorld:
    def __init__(self):
        self.frame = 0
        self.sensors = []
        self.ego = Mock(id=41, type_id="vehicle.motorcycle")
        self.ego.get_location.return_value = SimpleNamespace(x=-20.0, y=0.0)
        self.ego.get_transform.return_value = object()
        self.ego.get_velocity.return_value = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.ego.bounding_box.get_world_vertices.return_value = [SimpleNamespace(x=-19.0, y=0.0)]

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: Mock(id=name))

    def spawn_actor(self, blueprint, transform, attach_to):
        sensor = Mock(id=len(self.sensors) + 100)
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.frame * 0.05))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.world = FakeWorld()
        self.carla = SimpleNamespace(Transform=lambda *args: object(),
                                     Location=lambda *args: object(),
                                     Rotation=lambda *args: object(),
                                     VehicleControl=lambda **kwargs: kwargs)
        self.observer = SimpleNamespace(
            control=lambda *args: {"source_kind": "reviewed_native_controller",
                                   "throttle": 0, "brake": 1, "steer": 0},
            read_composite_head=lambda world, head, site, frame: {
                "source_kind": "native_device_readback", "official_head_id": site["official_head_id"],
                "lit_aspects": ["steady_red", "green_turn_arrow"]},
            read_participants=lambda *args: [])

    def _site(self):
        return {"original_sources": {"camera_ref": {"path": "camera.json", "sha256": "0" * 64}},
                "camera_source_ref": "camera_ref", "official_head_id": "head-17",
                "ego_approach_id": "west", "route_xy": [[-20, 0], [0, 0], [20, 0]],
                "camera_mounts": {name: {"width": 16, "height": 16, "fov": 90,
                                          "mount": {"xyz": [0, 0, 1],
                                                    "pitch_yaw_roll": [0, 0, 0]}}
                                  for name in adapter.VIEWS}}

    def test_live_actor_and_same_frame_camera_readback(self):
        site = self._site()
        session = adapter.Session(self.world, self.carla, site, self.observer)
        session.bind_native({"ego": self.world.ego, "head": object()}, site)
        row = session.tick()
        self.assertEqual(row["frame"], 1)
        self.assertEqual(row["ego_front_station_m"], -19.0)
        self.assertEqual(row["lit_aspects"], ["steady_red", "green_turn_arrow"])
        for queue in session.queues.values():
            queue.put(SimpleNamespace(frame=1, width=16, height=16,
                                      raw_data=b"\0" * 1024))
        views = session.read_views(1)
        self.assertEqual(len({x["sensor_id"] for x in views.values()}), 4)
        self.assertTrue(all(x["frame"] == row["frame"] for x in views.values()))
        session.close()
        self.assertTrue(all(sensor.destroy.called for sensor in self.world.sensors))

    def test_unreviewed_observer_and_bad_camera_frame_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet, site = make_site(Path(temporary))
            site["observer_source_ref"] = "missing"
            with self.assertRaisesRegex(ValueError, "reviewed Native observer source missing"):
                adapter._load_observer(site, packet.parent)
        site = self._site()
        session = adapter.Session(self.world, self.carla, site, self.observer)
        session.bind_native({"ego": self.world.ego, "head": object()}, site)
        for queue in session.queues.values():
            queue.put(SimpleNamespace(frame=2, width=16, height=16,
                                      raw_data=b"\0" * 1024))
        with self.assertRaisesRegex(ValueError, "camera frame mismatch"):
            session.read_views(1)
        session.close()

    def test_unreviewed_composite_fails_before_event_publication(self):
        site = self._site()
        observer = SimpleNamespace(**vars(self.observer))
        observer.read_composite_head = lambda *args: {"lit_aspects": ["steady_red"]}
        session = adapter.Session(self.world, self.carla, site, observer)
        session.bind_native({"ego": self.world.ego, "head": object()}, site)
        with self.assertRaisesRegex(ValueError, "original composite head readback required"):
            session.tick()
        session.close()


if __name__ == "__main__":
    unittest.main()
