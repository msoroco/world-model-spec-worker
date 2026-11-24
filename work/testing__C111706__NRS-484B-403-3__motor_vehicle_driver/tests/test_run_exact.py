import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_cameras import VIEWS
from run_exact import run_exact


def route(lanes):
    return [{"x": i * 2.0, "y": 0.0, "target_speed_mps": 3.0,
             "road_id": 7, "lane_id": lane,
             "junction_id": 3 if i == 1 else None}
            for i, lane in enumerate(lanes)]


class Actor:
    def __init__(self, actor_id):
        self.id = actor_id
        self.destroyed = False
        self.controls = []
    def apply_control(self, value):
        self.controls.append(value)
    def destroy(self):
        self.destroyed = True


class Sensor(Actor):
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True


class World:
    def __init__(self, *, fail_second=False):
        self.settings = type("Settings", (), {"synchronous_mode": False,
                            "fixed_delta_seconds": None})()
        self.applied = []
        self.actors = []
        self.fail_second = fail_second
    def get_settings(self):
        return self.settings
    def apply_settings(self, settings):
        self.settings = settings
        self.applied.append((settings.synchronous_mode, settings.fixed_delta_seconds))
    def get_map(self):
        return type("Map", (), {"name": "reviewed-map"})()
    def get_blueprint_library(self):
        return type("Library", (), {"find": lambda self, name: name})()
    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.actors:
            return None
        actor = Actor(len(self.actors) + 1)
        self.actors.append(actor)
        return actor


class ExactRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.case_id = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver__intersection_vehicle_near"
        site = {"case_id": self.case_id, "map_name": "reviewed-map",
                "map_sha256": "map-source", "route_sha256": "route-source",
                "district_source_sha256": "district-source",
                "intersection_boundary_source_sha256": "boundary-source",
                "intersection_boundary": {"source_sha256": "boundary-source",
                    "polygon_xy_m": [[0, 0], [1, 0], [0, 1]]},
                "ego_blueprint": "vehicle.test.ego", "other_blueprint": "vehicle.test.other",
                "ego_route": route([1, 1, -1]), "other_route": route([1, 1, 1]),
                "other_spawn": "other", "other_start_tick": 10}
        self.site_path = Path(self.tmp.name) / "site.json"
        self.site_path.write_text(json.dumps(site) + "\n")
        self.sha = hashlib.sha256(self.site_path.read_bytes()).hexdigest()
        self.output = Path(self.tmp.name) / "native.json"
        self.world = World()
        self.sensors = {name: Sensor(i + 10) for i, name in enumerate(VIEWS)}

    def run_case(self, capture_fn, *, camera_builder=None):
        return run_exact(self.world, site_path=self.site_path, site_sha256=self.sha,
                         case_id=self.case_id, ego_spawn="ego", other_spawn="other",
                         camera_builder=camera_builder or (lambda *_: self.sensors),
                         output=self.output,
                         control_factory=lambda **values: values,
                         capture_fn=capture_fn)

    def test_wires_exact_capture_and_restores_owned_resources(self):
        def capture_fn(world, ego, other, path, sha, case, output,
                       ego_control, other_control, brake, **kwargs):
            self.assertEqual((kwargs["ticks"], kwargs["step_s"]), (900, .05))
            self.assertEqual(world.applied[-1], (True, .05))
            self.assertEqual((ego.id, other.id), (1, 2))
            self.assertEqual((ego_control.route[0]["lane_id"],
                              other_control.start_tick), (1, 10))
            self.assertEqual(set(kwargs["camera_collector"].queues), set(VIEWS))
            return {"frame_count": 900}
        receipt = self.run_case(capture_fn)
        self.assertEqual(receipt["frame_count"], 900)
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(all(actor.destroyed and actor.controls[-1]["brake"] == 1
                            for actor in self.world.actors))
        self.assertTrue(all(sensor.destroyed and sensor.stopped
                            for sensor in self.sensors.values()))

    def test_capture_failure_restores_world_and_brakes(self):
        with self.assertRaisesRegex(RuntimeError, "readback failed"):
            self.run_case(lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("readback failed")))
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(all(actor.destroyed and actor.controls[-1]["brake"] == 1
                            for actor in self.world.actors))
        self.assertTrue(all(sensor.destroyed and sensor.stopped
                            for sensor in self.sensors.values()))

    def test_second_spawn_failure_restores_world(self):
        self.world.fail_second = True
        with self.assertRaisesRegex(ValueError, "other vehicle spawn failed"):
            self.run_case(lambda *args, **kwargs: None)
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(self.world.actors[0].destroyed)

    def test_rejects_duplicate_camera_actor_ids(self):
        self.sensors["approach"] = self.sensors["overview"]
        with self.assertRaisesRegex(ValueError, "four distinct"):
            self.run_case(lambda *args, **kwargs: None)
        self.assertEqual(self.world.applied[-1], (False, None))

    def test_sensor_stop_failure_still_restores_world_and_actors(self):
        def broken_stop():
            raise RuntimeError("sensor stop failed")
        self.sensors["overview"].stop = broken_stop
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            self.run_case(lambda *args, **kwargs: {"frame_count": 900})
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(all(actor.destroyed for actor in self.world.actors))
        self.assertTrue(all(sensor.destroyed for sensor in self.sensors.values()))


if __name__ == "__main__":
    unittest.main()
