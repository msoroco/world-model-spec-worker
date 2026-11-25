"""Fake Native world verifies tick identity and restoration without CARLA."""
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner


class NativeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        plan = (ROOT / "case-plan.json").read_bytes()
        (self.root / "case-plan.json").write_bytes(plan)
        case = ROOT.name + "__arrow_clear"
        (self.root / "config.json").write_text(json.dumps({
            "plan_sha256": hashlib.sha256(plan).hexdigest(), "selected_case_id": case,
            "assignment_id": ROOT.name, "case_suffix": "arrow_clear",
            "construction_plan": json.loads(plan)["cases"][0]["construction"],
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": runner.CAMERAS}))
        refs = []
        for name in ("map", "signal", "route", "crosswalk"):
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"source": name}))
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.site = {"cell_id": "C111610", "actor": "motor_vehicle_driver",
                     "source_kind": "original_native_site_review",
                     "case_id": case, "original_sources": refs,
                     "map_source_path": "map.json", "signal_source_path": "signal.json",
                     "route_source_path": "route.json", "crosswalk_source_path": "crosswalk.json",
                     "native_map_name": "TownTest", "official_head_id": "17",
                     "ego_approach_id": "north", "facing_relation": True,
                     "arrow_movement": "left", "ego_route_xy": [[0,-8],[0,0],[-8,0]],
                     "intersection_polygon_xy": [[-3,-3],[3,-3],[3,3],[-3,3]],
                     "adjacent_crosswalk_polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]],
                     "signal_source_mode": "native_head_plus_external_aspect_packet",
                     "spawn_z_m": 0.5, "ego_yaw_deg": 90,
                     "ego_blueprint_id": "vehicle.test"}
        (self.root / "site.json").write_text(json.dumps(self.site))
        self.settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.actor = types.SimpleNamespace(id=1, destroyed=False)
        self.actor.destroy = lambda: setattr(self.actor, "destroyed", True)
        owner = self
        class World:
            frame = 0
            def get_settings(self): return owner.settings
            def apply_settings(self, settings):
                owner.settings = types.SimpleNamespace(
                    synchronous_mode=settings.synchronous_mode,
                    fixed_delta_seconds=settings.fixed_delta_seconds)
            def get_blueprint_library(self): return types.SimpleNamespace(find=lambda ident: ident)
            def get_map(self):
                class Map:
                    name = "TownTest"
                    def get_waypoint(self, location):
                        return types.SimpleNamespace(transform=types.SimpleNamespace(location=location))
                    def get_crosswalks(self):
                        return [types.SimpleNamespace(x=x,y=y)
                                for x,y in ((3,-3),(6,-3),(6,3),(3,3))]
                return Map()
            def get_actors(self): return types.SimpleNamespace(filter=lambda pattern: [types.SimpleNamespace(id=17)])
            def try_spawn_actor(self, blueprint, pose): return owner.actor
            def tick(self):
                self.frame += 1
                return self.frame
        self.world = World()
        class Client:
            def __init__(self, host, port): pass
            def set_timeout(self, seconds): pass
            def get_world(self): return owner.world
        self.carla = types.SimpleNamespace(Client=Client,
            Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
            Rotation=lambda **kwargs: kwargs,
            Transform=lambda location, rotation: (location, rotation))

    def tearDown(self):
        self.temporary.cleanup()

    def exercise(self, faulty=None):
        owner = self
        class Adapter:
            def bind(self, world, carla, site, actors, output): return object()
            def command(self, state, index): pass
            def read(self, state, frame, index):
                aspect = {"frame": frame}
                event = {"frame": frame}
                images = {name: {"frame": frame} for name in runner.CAMERAS}
                if faulty == "aspect": aspect["frame"] += 1
                if faulty == "camera": images["approach"]["frame"] += 1
                return aspect, event, images
            def close(self, state): owner.closed = True
        self.closed = False
        def capture(site, output, step, frames):
            self.assertEqual(frames, 900)
            for index in range(3): step(index)
            return {"frame_count": frames}
        with patch.dict(sys.modules, {"carla": self.carla}), \
             patch.object(runner, "_adapter", return_value=Adapter()), \
             patch.object(runner, "capture_with_cameras", side_effect=capture):
            return runner.run_native(self.root, self.root / "attempt", "localhost", 2000)

    def test_fake_world_capture_and_restore(self):
        self.assertEqual(self.exercise()["frame_count"], 900)
        self.assertEqual(self.world.frame, 3)
        self.assertEqual((self.root / "attempt/site.json").read_bytes(),
                         (self.root / "site.json").read_bytes())
        self.assertEqual((self.root / "attempt/map.json").read_bytes(),
                         (self.root / "map.json").read_bytes())
        self.assertTrue(self.actor.destroyed)
        self.assertTrue(self.closed)
        self.assertFalse(self.settings.synchronous_mode)
        self.assertIsNone(self.settings.fixed_delta_seconds)

    def test_frame_mismatch_rejected_and_world_restored(self):
        with self.assertRaisesRegex(ValueError, "same-tick frame identity"):
            self.exercise("camera")
        self.assertTrue(self.actor.destroyed)
        self.assertFalse(self.settings.synchronous_mode)

    def test_aspect_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "same-tick frame identity"):
            self.exercise("aspect")


if __name__ == "__main__":
    unittest.main()
