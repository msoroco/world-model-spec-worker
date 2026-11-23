import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from test_source_tick_capture import GEOMETRY, CONTEXT, body, capture


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("physical_completion", ROOT / "physical_completion.py")
physical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(physical)


def make_attempt(directory, *, last_x=13):
    writer = capture.TickCapture(Path(directory), GEOMETRY, CONTEXT)
    for index, x in enumerate((-9, -5, 0, 5, last_x)):
        y = (-8, -3, 4, 4, 12)[index]
        writer.append({"frame": 400 + index, "time_s": index * .05,
            "ego": {"body_vertices_xy_m": body(x, 5), "velocity_xy_mps": [3, 0]},
            "through_vehicle": {"center_xy_m": [5, y], "body_vertices_xy_m": body(5, y)},
            "visibility_probe": {"source": "native_raycast", "occluded": index == 0,
                                 "origin_xy_m": [x, 5], "target_xy_m": [5, y]},
            "sign_present": True})
    writer.close()
    return writer


class PhysicalCompletionTests(unittest.TestCase):
    def test_complete_full_body_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            make_attempt(directory)
            result = physical.assess(Path(directory), "exact-case", "a" * 64, diagnostic_fixture=True)
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "met")
            self.assertTrue(result["maneuver_completed"])
            self.assertEqual(result["realized_observables"]["sample_count"], 5)
            self.assertEqual(result["provenance_kind"], "synthetic_fixture")

    def test_still_in_intersection_is_not_met(self):
        with tempfile.TemporaryDirectory() as directory:
            make_attempt(directory, last_x=5)
            result = physical.assess(Path(directory), "exact-case", "a" * 64, diagnostic_fixture=True)
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "not_met")
            self.assertFalse(result["maneuver_completed"])

    def test_missing_source_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            result = physical.assess(Path(directory), "exact-case", "a" * 64, diagnostic_fixture=True)
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "unverified")
            self.assertFalse(result["maneuver_completed"])

    def test_changed_original_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = make_attempt(directory)
            with writer.path.open("a") as stream:
                stream.write("{}\n")
            result = physical.assess(Path(directory), "exact-case", "a" * 64, diagnostic_fixture=True)
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "unverified")
            self.assertIn("source hash differs", result["physical_checks"]["maneuver"]["reason"])


if __name__ == "__main__":
    unittest.main()
