import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capture_roundabout import capture
from roundabout_measurements import measure
import test_native_roundabout as source_module


class CaptureTests(unittest.TestCase):
    def setUp(self):
        source = source_module.NativeConstructionTests("test_source_bound_case_and_two_spawns")
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.source = source
        self.output = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.output))

        class World:
            frame = 0
            def get_settings(self):
                return type("Settings", (), {"synchronous_mode": True,
                    "fixed_delta_seconds": .05})()
            def get_map(self):
                return type("Map", (), {"name": "reviewed-map"})()
            def tick(self):
                self.frame += 1
                return self.frame
            def get_snapshot(self):
                return type("Snapshot", (), {"frame": self.frame,
                    "timestamp": type("Time", (), {"elapsed_seconds": self.frame * .05})()})()
        self.world = World()

        class Actor:
            def __init__(self, actor_id):
                self.id = actor_id
            def get_velocity(self):
                return type("Velocity", (), {"x": 1., "y": 0., "z": 0.})()
        self.ego, self.other = Actor(10), Actor(11)
        self.controls = []
        self.brakes = []

    def body(self, actor):
        y = -5 if self.world.frame == 1 else (-3 if self.world.frame == 2 else 0)
        x = 0 if actor is self.ego else 1
        if actor is self.other:
            y = 0
        return [[x + dx, y + dy, z] for z in (-.5, .5)
                for dx in (-.5, .5) for dy in (-.5, .5)]

    def run_capture(self, ticks):
        path = self.source.map_path
        return capture(self.world, self.ego, self.other, path,
                       hashlib.sha256(path.read_bytes()).hexdigest(),
                       self.source.case, self.output,
                       lambda actor, tick: self.controls.append((actor.id, tick)),
                       lambda actor, tick: self.controls.append((actor.id, tick)),
                       self.body, lambda actor: self.brakes.append(actor.id),
                       ticks=ticks)

    def test_full_original_trace_joins_saved_measurement(self):
        receipt = self.run_capture(900)
        data = json.loads(pathlib.Path(receipt["receipt"]).read_text())
        self.assertFalse(data["diagnostic_fixture"])
        self.assertEqual(data["frame_count"], 900)
        self.assertEqual(self.controls[:4], [(10, 0), (11, 0), (10, 1), (11, 1)])
        measured = measure(case_id=self.source.case, map_path=self.source.map_path,
                           trace_path=receipt["trace"], receipt_path=receipt["receipt"])
        self.assertEqual(measured["first_observed_ego_entry_frame"], 2)
        self.assertTrue(measured["opponent_in_ring_at_ego_entry"])

    def test_short_capture_is_diagnostic_and_not_delivery(self):
        receipt = self.run_capture(3)
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            measure(case_id=self.source.case, map_path=self.source.map_path,
                    trace_path=receipt["trace"], receipt_path=receipt["receipt"])

    def test_frame_failure_brakes_both_and_leaves_no_source(self):
        original_tick = self.world.tick
        self.world.tick = lambda: original_tick() + 1
        with self.assertRaisesRegex(ValueError, "frame/time discontinuity"):
            self.run_capture(3)
        self.assertEqual(self.brakes, [10, 11])
        self.assertFalse((self.output / "original-trace.jsonl").exists())
        self.assertFalse((self.output / "source-receipt.json").exists())

    def test_wrong_world_rate_rejected_before_control(self):
        self.world.get_settings = lambda: type("Settings", (), {
            "synchronous_mode": True, "fixed_delta_seconds": .1})()
        with self.assertRaisesRegex(ValueError, "synchronous at 20 Hz"):
            self.run_capture(3)
        self.assertEqual(self.controls, [])

    def test_missing_original_body_brakes_and_refuses_receipt(self):
        self.body = lambda actor: [[0, 0, 0]]
        with self.assertRaisesRegex(ValueError, "eight original body vertices"):
            self.run_capture(3)
        self.assertEqual(self.brakes, [10, 11])
        self.assertFalse((self.output / "source-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
