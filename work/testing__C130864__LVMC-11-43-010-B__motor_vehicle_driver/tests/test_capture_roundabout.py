import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from io import BytesIO

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capture_roundabout import CAMERAS, capture
from saved_roundabout_camera_audit import audit_saved
from roundabout_delivery_audit import audit_delivery
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

    def run_capture(self, ticks, **options):
        path = self.source.map_path
        return capture(self.world, self.ego, self.other, path,
                       hashlib.sha256(path.read_bytes()).hexdigest(),
                       self.source.case, self.output,
                       lambda actor, tick: self.controls.append((actor.id, tick)),
                       lambda actor, tick: self.controls.append((actor.id, tick)),
                       self.body, lambda actor: self.brakes.append(actor.id),
                       ticks=ticks, **options)

    def camera_options(self):
        image = Image.new("RGB", (4, 3), (24, 68, 102))
        output = BytesIO()
        image.save(output, format="PNG")
        payload = output.getvalue()
        return {"camera_dimensions": {name: (4, 3) for name in CAMERAS},
                "camera_readers": {name: lambda frame, data=payload:
                    {"frame": frame, "png_bytes": data} for name in CAMERAS}}

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

    def test_full_four_camera_saved_decode_and_source_binding(self):
        options = self.camera_options()
        receipt = self.run_capture(900, **options)
        result = audit_saved(case_id=self.source.case, map_path=self.source.map_path,
                             trace_path=receipt["trace"], receipt_path=receipt["receipt"],
                             camera_dimensions=options["camera_dimensions"])
        self.assertEqual(result["decoded_images"], 3600)
        self.assertEqual(set(result["camera_source_sha256"]), set(CAMERAS))
        delivery = audit_delivery(case_id=self.source.case, map_path=self.source.map_path,
                                  trace_path=receipt["trace"], receipt_path=receipt["receipt"],
                                  camera_dimensions=options["camera_dimensions"])
        self.assertEqual(delivery["decoded_images"], 3600)
        self.assertFalse(delivery["physical_acceptance"])
        video = self.output / "original-overview.png.zip"
        with video.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            audit_saved(case_id=self.source.case, map_path=self.source.map_path,
                        trace_path=receipt["trace"], receipt_path=receipt["receipt"],
                        camera_dimensions=options["camera_dimensions"])

    def test_camera_frame_failure_brakes_and_refuses_source(self):
        options = self.camera_options()
        options["camera_readers"]["approach"] = lambda frame: {
            "frame": frame + 1, "png_bytes": b""}
        with self.assertRaisesRegex(ValueError, "camera frame identity"):
            self.run_capture(3, **options)
        self.assertEqual(self.brakes, [10, 11])
        self.assertFalse((self.output / "original-receipt.json").exists())
        self.assertFalse(list(self.output.glob("*.png.zip")))

    def test_frame_failure_brakes_both_and_leaves_no_source(self):
        original_tick = self.world.tick
        self.world.tick = lambda: original_tick() + 1
        with self.assertRaisesRegex(ValueError, "frame/time discontinuity"):
            self.run_capture(3)
        self.assertEqual(self.brakes, [10, 11])
        self.assertFalse((self.output / "original-trace.jsonl").exists())
        self.assertFalse((self.output / "original-receipt.json").exists())

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
        self.assertFalse((self.output / "original-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
