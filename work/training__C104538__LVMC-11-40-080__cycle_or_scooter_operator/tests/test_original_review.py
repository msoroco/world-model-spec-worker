import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("selected_original_finalizer", ROOT / "finalize.py")
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


class OriginalReviewTest(unittest.TestCase):
    def test_reviewed_channels_preserve_original_acquisition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "channels").mkdir()
            original = root / "channels" / "ru.rider_posture.jsonl"
            original.write_text('{"time_s": 0.05, "value": {"original_pixel_review": "pending"}}\n')
            before = original.read_bytes()
            survey = {"official_sign_status": "unreviewed", "original_pixel_visibility": "unreviewed"}
            (root / "road_geometry.json").write_text(json.dumps(survey) + "\n")
            (root / "context.json").write_text(json.dumps({"signed_hill_crest": survey}) + "\n")
            description = {"channels": [{"name": "ru.rider_posture"}]}
            native = [{"time_s": .05}]
            rider = [{"mounted": True}]
            finalizer.rebuild_channels(root, description, native, [{}], rider, [{}], {}, True)
            self.assertEqual(original.read_bytes(), before)
            reviewed = root / "reviewed_channels" / "ru.rider_posture.jsonl"
            self.assertTrue(reviewed.is_file())
            self.assertEqual(json.loads(reviewed.read_text())["value"]["mounted"], True)

    def test_sealed_original_review_and_mutations(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = [{"frame": 0, "time_s": .05, "actor_id": "42", "mounted": None,
                    "walking_machine": None, "u_turn_active": None}]
            native = [{"native_frame": 7, "time_s": .05}]
            mapping = [{"native_frame": 7, "carla_frame": 7, "video_frame": 0, "time_s": .05}]
            sign = {"code": "no_u_turn", "station_m": 72.0}
            sources = ("rider_native_samples.jsonl", "native_samples.jsonl",
                       "video_frames.jsonl", "authored-sign.json", "trace.jsonl",
                       "body_history.jsonl", "capture/evidence.jsonl",
                       "overview.mkv", "approach.mkv", "reference_corner.mkv",
                       "driver_reference.mkv")
            for name in sources:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name + "\n")
            seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
                    "diagnostic_fixture": False, "frames": 1,
                    "restoration": {"restored": True},
                    "sources": {name: finalizer.sha(root / name) for name in sources}}
            (root / "capture-seal.json").write_text(json.dumps(seal) + "\n")
            labels = [{"frame": 0, "time_s": .05, "actor_id": "42",
                       "mounted": True, "walking_machine": False, "u_turn_active": True}]
            pixels = [{"frame": 0, "carla_frame": 7, "sign_visible": True,
                       "rider_visible": True, "machine_visible": True}]
            (root / "rider-review.jsonl").write_text(json.dumps(labels[0]) + "\n")
            (root / "pixel_review.jsonl").write_text(json.dumps(pixels[0]) + "\n")
            camera_names = ("overview", "approach", "reference_corner", "driver_reference")
            review = {"source_kind": "original_camera_sign_and_rider_review",
                      "reviewer": "unit-reviewer", "reviewed_from_original_pixels": True,
                      "official_device_verified": True, "governs_approach": True,
                      "rider_posture_verified": True, "sign_code": "no_u_turn",
                      "pedestrian_rule_compliance_verified": True,
                      "native_samples_sha256": finalizer.sha(root / "native_samples.jsonl"),
                      "frame_map_sha256": finalizer.sha(root / "video_frames.jsonl"),
                      "rider_samples_sha256": finalizer.sha(root / "rider_native_samples.jsonl"),
                      "rider_review_sha256": finalizer.sha(root / "rider-review.jsonl"),
                      "pixel_review_sha256": finalizer.sha(root / "pixel_review.jsonl"),
                      "camera_source_sha256": {name + ".mkv": finalizer.sha(root / (name + ".mkv"))
                                               for name in camera_names}}
            (root / "sign-review.json").write_text(json.dumps(review) + "\n")
            previous = sys.modules.get("measure_geometry")
            sys.modules["measure_geometry"] = types.SimpleNamespace(
                measure=lambda *_: {"u_turn_geometry_observed": True})
            try:
                manifest = {"source_kind": "original_native_capture_unreviewed",
                            "original_native_capture_executed": True}
                observed, returned_review, geometry = finalizer.reviewed_original_rows(
                    root, {"case_suffix": "mounted_turn"}, manifest, native, mapping, raw, sign)
                self.assertTrue(observed[0]["mounted"])
                self.assertIs(returned_review["official_device_verified"], True)
                self.assertTrue(geometry["u_turn_geometry_observed"])
                (root / "approach.mkv").write_text("changed\n")
                with self.assertRaisesRegex(ValueError, "sealed source differs"):
                    finalizer.reviewed_original_rows(root, {"case_suffix": "mounted_turn"},
                                                     manifest, native, mapping, raw, sign)
                (root / "approach.mkv").write_text("approach.mkv\n")
                review["reviewer"] = ""
                (root / "sign-review.json").write_text(json.dumps(review) + "\n")
                with self.assertRaisesRegex(ValueError, "review source binding differs"):
                    finalizer.reviewed_original_rows(root, {"case_suffix": "mounted_turn"},
                                                     manifest, native, mapping, raw, sign)
            finally:
                if previous is None:
                    sys.modules.pop("measure_geometry", None)
                else:
                    sys.modules["measure_geometry"] = previous


if __name__ == "__main__":
    unittest.main()
