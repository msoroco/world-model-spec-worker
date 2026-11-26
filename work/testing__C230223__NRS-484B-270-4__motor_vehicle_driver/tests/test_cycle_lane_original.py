"""Exercise source custody and exact saved-frame joins with synthetic bytes."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from cycle_lane_original import audit
from cycle_lane_intersection import ASSIGNMENT


def write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value) + "\n")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def body_polygon(in_intersection, in_lane):
    x = 5 if in_intersection else -1
    y = 4 if in_lane else 8
    return [[x - 0.1, y - 0.1], [x + 0.1, y - 0.1],
            [x + 0.1, y + 0.1], [x - 0.1, y + 0.1]]


class OriginalAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c230223-unit"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.case_id = ASSIGNMENT + "__cycle_lane_through_intersection"
        self.site = write(self.root, "site.json", {
            "assignment_id": ASSIGNMENT, "source_kind": "original_reviewed",
            "map_id": "synthetic-test-map", "intersection_id": "I", "cycle_lane_id": "L",
            "cycle_lane_designated_for": "bicycle", "designation_authority": "test-review",
            "intersection_is_public_highway_junction": True, "not_alley_junction": True,
            "intersection_polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "cycle_lane_polygon": [[-2, 3], [10, 3], [10, 5], [-2, 5]],
            "route_candidates": {"test_route": [[-2, 4], [12, 4]],
                                 "before_route": [[-2, 4], [-1, 4], [-1, 8], [12, 8]],
                                 "ordinary_route": [[-2, 8], [12, 8]]}})
        self.exception = write(self.root, "exception.json", {
            "source_kind": "original_reviewed", "law_id": "NRS-484B-270-3",
            "status": "does_not_apply", "authoritative_clause": "synthetic test clause",
            "reviewer": "test-only"})
        self.vehicle = write(self.root, "vehicle.json", {
            "source_kind": "original_reviewed", "vehicle_type": "motor_vehicle",
            "actor_id": 7, "blueprint_id": "vehicle.synthetic.test",
            "driver_identity_source": "test-only"})
        self.rows = [{"frame": i + 1, "time_s": i * 0.05, "ego_actor_id": 7,
                      "ego_body_in_intersection": 200 <= i < 600,
                      "ego_body_in_designated_cycle_lane": 100 <= i < 700,
                      "ego_body_polygon": body_polygon(200 <= i < 600, 100 <= i < 700)}
                     for i in range(900)]
        self.history = write(self.root, "history.json", self.rows)
        cameras = {}
        for view in ("overview", "approach", "reference_corner", "driver_reference"):
            path = self.root / (view + ".mkv")
            path.write_bytes(b"synthetic-test-video")
            cameras[view] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.seal = {"format": "cycle-lane-native-attempt-v1",
                     "source_kind": "original_native", "diagnostic_fixture": False,
                     "case_id": self.case_id, "site": self.site,
                     "spawned_actor_id": 7,
                     "vehicle_blueprint_id": "vehicle.synthetic.test",
                     "subsection_3": self.exception, "vehicle": self.vehicle,
                     "history": self.history, "cameras": cameras,
                     "capture_profile": {"duration_s": 45, "hz": 20,
                                         "views": ["overview", "approach", "reference_corner", "driver_reference"],
                                         "controller_policy": "fixed-test-policy"},
                     "route_candidate_id": "test_route"}
        write(self.root, "attempt-source.json", self.seal)

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        return audit(self.root, self.site["sha256"], self.exception["sha256"],
                     self.vehicle["sha256"])

    def test_900_original_frame_measurement(self):
        result = self.check()
        self.assertEqual(result["intersection_cycle_lane_overlap_frames"], 400)
        self.assertIsNone(result["legal_verdict"])

    def test_missing_review_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "independent reviewed site hash"):
            audit(self.root, "0" * 64, self.exception["sha256"], self.vehicle["sha256"])

    def test_diagnostic_provenance_rejected(self):
        self.seal["diagnostic_fixture"] = True
        write(self.root, "attempt-source.json", self.seal)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.check()

    def test_frame_gap_rejected(self):
        self.rows[450]["frame"] += 2
        write(self.root, "history.json", self.rows)
        with self.assertRaisesRegex(ValueError, "original source changed"):
            self.check()

    def test_changed_camera_rejected(self):
        (self.root / "overview.mkv").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "original camera changed"):
            self.check()

    def test_false_body_occupation_rejected(self):
        self.rows[450]["ego_body_in_designated_cycle_lane"] = False
        self.seal["history"] = write(self.root, "history.json", self.rows)
        write(self.root, "attempt-source.json", self.seal)
        with self.assertRaisesRegex(ValueError, "occupation disagrees"):
            self.check()


if __name__ == "__main__":
    unittest.main()
