"""CPU checks for the authored obstruction capture and original-source gates."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "native"))

from geometry import check as check_geometry, largest_open_width
from measure_obstruction import measure
from prove_obstruction import _row, _write
from runner import barrier_blueprint, check, reviewed_context
from source_join import check as check_source_join


class NativeDraftTests(unittest.TestCase):
    def test_both_exact_cases(self):
        for suffix in ("condition_a", "condition_b"):
            with self.subTest(suffix=suffix):
                config = ROOT / "native" / ("config-" + suffix + ".json")
                proof = check(config)
                self.assertTrue(proof["passed"])
                self.assertFalse(proof["physical_acceptance_claimed"])
        geometry = check_geometry()
        self.assertLess(geometry["authored_openings_m"]["condition_a"], 1.8)
        self.assertGreater(geometry["authored_openings_m"]["condition_b"], 1.8)
        self.assertAlmostEqual(largest_open_width((-100, -3.5, 100, 3.5),
                               [(0, 1, 5, 3.4), (0, -2, 5, -.2)]), 1.5)

    def test_camera_and_verdict_damage_rejected(self):
        source = json.loads((ROOT / "native/config-condition_a.json").read_text())
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            path = Path(temp) / "config.json"
            for change, phrase in ((lambda d: d["cameras"].pop(), "Four named camera"),
                                   (lambda d: d.update(legal_verdict_claimed=True), "Unobserved outcome"),
                                   (lambda d: d.update(park_y_m=-2.5), "parked position")):
                damaged = json.loads(json.dumps(source))
                change(damaged)
                path.write_text(json.dumps(damaged) + "\n")
                with self.assertRaisesRegex(ValueError, phrase):
                    check(path)

    def test_original_authority_source_binding(self):
        case = json.loads((ROOT / "native/config-condition_a.json").read_text())["case_id"]
        names = ("traffic_conflict", "law_direction", "police_direction", "traffic_device")
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            folder = Path(temp)
            records = {}
            for name in names:
                path = folder / (name + ".txt")
                path.write_text("original source review field: " + name + "\n")
                records[name] = {"path": path.name,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            context = {"case_id": case, "source_kind": "reviewed_authority_context",
                       "exceptions": {name: False for name in names},
                       "exception_source": {name + "_reviewed": True for name in names},
                       "source_records": records}
            path = folder / "context.json"
            path.write_text(json.dumps(context) + "\n")
            reviewed_context(path, case)
            (folder / "police_direction.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "Missing or changed authority source"):
                reviewed_context(path, case)

    def test_barrier_asset_required(self):
        class Library:
            def filter(self, pattern):
                self.pattern = pattern
                return []

        with self.assertRaisesRegex(ValueError, "physical excavation barrier asset"):
            barrier_blueprint(Library())

    def test_original_frame_join_and_damaged_camera(self):
        views = ("overview", "approach", "reference_corner", "driver_reference")
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            folder = Path(temp)
            sample = []
            mapping = []
            camera = []
            for index in range(600):
                native = 370 + index
                sample.append({"native_frame": native, "time_s": index / 20,
                               "source_kind": "original_native"})
                mapping.append({"native_frame": native, "video_frame": index,
                                "time_s": index / 20,
                                "camera_native_frames": {view: native for view in views}})
                camera.extend({"frame": index, "native_frame": native, "camera": view,
                               "source_kind": "original_native", "rgb_sha256": "a" * 64}
                              for view in views)
            def write(name, rows):
                (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
            write("native_samples.jsonl", sample)
            write("video_frames.jsonl", mapping)
            write("camera-frames.jsonl", camera)
            self.assertEqual(check_source_join(folder)["camera_frames"], 2400)
            camera[10]["native_frame"] += 1
            write("camera-frames.jsonl", camera)
            with self.assertRaisesRegex(ValueError, "camera source join"):
                check_source_join(folder)

    def test_native_frame_base_is_original_not_assumed_zero(self):
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            path = Path(temp) / "samples.jsonl"
            values = [_row(index, True) for index in range(600)]
            for index, value in enumerate(values):
                value["native_frame"] = index + 370
            digest = _write(path, values)
            self.assertEqual(measure(path, digest)["frames"], 600)
            values[300]["native_frame"] += 1
            digest = _write(path, values)
            with self.assertRaisesRegex(ValueError, "Native frame/time join"):
                measure(path, digest)


if __name__ == "__main__":
    unittest.main()
