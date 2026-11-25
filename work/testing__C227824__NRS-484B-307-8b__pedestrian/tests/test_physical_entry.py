import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "physical_entry.py"
SPEC = importlib.util.spec_from_file_location("c227824_physical_entry", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PhysicalEntryTests(unittest.TestCase):
    def setUp(self):
        self.scene = {"case_id": "case", "entry_request": "entry",
                      "highway_polygon_xy_m": [[0, 0], [2, 0], [2, 2], [0, 2]]}
        self.outside = [[-2, 0], [-1, 0], [-1, 1], [-2, 1]]
        self.inside = [[.5, .5], [1, .5], [1, 1], [.5, 1]]
        self.rows = [{"case_id": "case", "frame": i + 1, "time_s": (i + 1) * .05,
                      "body_polygon_xy_m": body}
                     for i, body in enumerate((self.outside, self.inside, self.inside))]
        self.report = {"case_id": "case", "sample_count": 3,
                       "measurement": {"first_entry": {"frame": 2}},
                       "source_sha256": {name: "a" * 64 for name in (
                           "scene.json", "walker-body-history.jsonl", "video_frames.jsonl")}}

    def test_entry_and_wait_source_patterns(self):
        entry = MODULE.assess(self.report, self.scene, self.rows)
        self.assertEqual(entry["status"], "met")
        self.assertFalse(entry["legal_verdict_claimed"])
        self.scene["entry_request"] = "wait"
        self.rows[1]["body_polygon_xy_m"] = self.outside
        self.rows[2]["body_polygon_xy_m"] = self.outside
        self.report["measurement"]["first_entry"] = None
        wait = MODULE.assess(self.report, self.scene, self.rows)
        self.assertEqual(wait["status"], "met")
        self.rows[2]["body_polygon_xy_m"] = self.inside
        self.report["measurement"]["first_entry"] = {"frame": 3}
        self.assertEqual(MODULE.assess(self.report, self.scene, self.rows)["status"],
                         "not_met")

    def test_rejects_changed_first_contact_and_missing_source(self):
        self.report["measurement"]["first_entry"] = {"frame": 3}
        with self.assertRaisesRegex(ValueError, "first-contact frame differs"):
            MODULE.assess(self.report, self.scene, self.rows)
        self.report["measurement"]["first_entry"] = {"frame": 2}
        del self.report["source_sha256"]["scene.json"]
        with self.assertRaisesRegex(ValueError, "source hashes missing"):
            MODULE.assess(self.report, self.scene, self.rows)


if __name__ == "__main__":
    unittest.main()
