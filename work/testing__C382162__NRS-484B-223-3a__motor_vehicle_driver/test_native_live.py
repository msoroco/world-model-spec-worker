import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import native_live
from native_capture import ASSIGNMENT, VIEWS


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = "clear"
        self.count = 0

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: "map")

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, value):
        self.settings = copy.copy(value)

    def get_weather(self):
        return self.weather

    def set_weather(self, value):
        self.weather = value

    def tick(self):
        self.count += 1
        return self.count

    def get_snapshot(self):
        return SimpleNamespace(frame=self.count,
                               timestamp=SimpleNamespace(elapsed_seconds=self.count * .05))


class Actor:
    def __init__(self):
        self.id, self.type_id, self.is_alive = 7, "vehicle.test", True
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda transform: [
            SimpleNamespace(x=i, y=0, z=0) for i in range(8)])

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=0, y=0, z=0),
                               get_forward_vector=lambda: SimpleNamespace(x=1, y=0))

    def get_velocity(self):
        return SimpleNamespace(length=lambda: 2.0)

    def destroy(self):
        self.is_alive = False


class Sensor:
    def __init__(self):
        self.stopped = self.destroyed = False

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Operator:
    def __init__(self, actor):
        self.actor = actor
        self.sensors = [Sensor() for _ in VIEWS]

    def site_readback(self, world, site):
        return dict(site)

    def spawn_vehicle(self, world, site, case_id):
        return self.actor

    def cameras(self, world, vehicle, views):
        return {view: lambda frame: object() for view in views}, self.sensors

    def control(self, vehicle, site, case_id, index):
        pass

    def observe(self, world, vehicle, site, frame):
        return {"source_frame_id": frame, "actor_id": vehicle.id,
                "driver_id": "ego", "road_id": "H", "lane_id": "C",
                "maneuver": "travel"}


class NativeLiveTests(unittest.TestCase):
    def test_world_and_actors_restored_after_capture(self):
        world, actor = World(), Actor()
        operator = Operator(actor)
        site = {"lanes": [], "junction": {}, "route": {},
                "highway_road_id": "H", "driver_id": "ego"}
        case = ASSIGNMENT + "__turn_from_highway"
        with patch.object(native_live, "verify_reviewed_site", return_value={}), \
             patch.object(native_live, "camera_reader", side_effect=lambda root, reader, dims: reader), \
             patch.object(native_live, "capture_original", side_effect=lambda root, cid, packet, intent, map_data, reader, count: reader(0)):
            result = native_live.capture(world, attempt_root=".runtime-work/c382162-owner",
                                         case_id=case, site=site, purpose_binding={},
                                         operator=operator, count=3)
        self.assertEqual(result["actor_id"], 7)
        self.assertFalse(world.settings.synchronous_mode)
        self.assertFalse(actor.is_alive)
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in operator.sensors))

    def test_source_gate_precedes_motion(self):
        world, actor = World(), Actor()
        operator = Operator(actor)
        with patch.object(native_live, "verify_reviewed_site", side_effect=ValueError("reviewed source hash mismatch")):
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                native_live.capture(world, attempt_root=".runtime-work/c382162-owner",
                                    case_id=ASSIGNMENT + "__turn_from_highway",
                                    site={}, purpose_binding={}, operator=operator)
        self.assertEqual(world.count, 0)
        self.assertTrue(actor.is_alive)


if __name__ == "__main__":
    unittest.main()
