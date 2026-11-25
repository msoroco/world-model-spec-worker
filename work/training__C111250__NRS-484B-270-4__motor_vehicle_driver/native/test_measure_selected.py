"""Source-shape unit tests only; these rows are not original CARLA evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from measure_selected import measure


REPO = Path(__file__).resolve().parents[3]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class SavedSourceTest(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="c111250-source-shape-", dir=scratch)
        self.root = Path(self.temp.name)
        write(self.root / "facility-context.json", {
            "source_kind": "original_native_capture", "facility_x_m": [3.5, 5.5],
            "intersection_y_m": [-7.0, 7.0], "native_map_sha256": "mock-map",
            "native_lane_survey": [{"lane_id": -1 if i % 2 == 0 else -2}
                                   for i in range(6)], "official_designation_proven": False})
        write(self.root / "subsection3-context.json", {
            "source_kind": "original_native_capture",
            "exception_clause_requested": "NRS 484B.270(3)(c), to avoid conflict with other traffic",
            "conflict_actor_id": 99,
            "conflict_actor_body_xy_m": [[1, -4], [2, -4], [2, -2], [1, -2]],
            "exception_legally_resolved": False})
        records = {name: [] for name in ("body-history.jsonl", "trace.jsonl",
                                      "video_frames.jsonl", "capture/evidence.jsonl")}
        for index in range(600):
            frame = 1000 + index; time = (index + 1) / 20
            y = -60 + .2 * index; x = 4.45
            records["body-history.jsonl"].append({
                "native_frame": frame, "time_s": time,
                "body_xy_m": [[x-.9, y-1], [x+.9, y-1], [x+.9, y+1], [x-.9, y+1]],
                "speed_mps": 4.0, "source_kind": "original_native_capture"})
            records["trace.jsonl"].append({"frame": frame, "time_s": time})
            records["video_frames.jsonl"].append({
                "native_frame": frame, "carla_frame": frame,
                "time_s": time, "video_frame": index})
            records["capture/evidence.jsonl"].append({"original_frame": frame})
        for name, rows in records.items():
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def tearDown(self):
        self.temp.cleanup()

    def test_original_shape_measures_overlap_without_legal_claim(self):
        result = measure(self.root)
        self.assertEqual(result["frames"], 600)
        self.assertGreater(result["cycle_lane_intersection_overlap_frames"], 0)
        self.assertFalse(result["legal_verdict_claimed"])
        self.assertFalse(result["subsection3_exception_legally_resolved"])

    def test_missing_exception_context_rejects(self):
        (self.root / "subsection3-context.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required original source"):
            measure(self.root)

    def test_synthetic_context_rejects(self):
        path = self.root / "facility-context.json"
        context = json.loads(path.read_text()); context["source_kind"] = "synthetic_cpu_diagnostic"
        write(path, context)
        with self.assertRaisesRegex(ValueError, "Original Native context"):
            measure(self.root)

    def test_explicit_diagnostic_mode_remains_labeled_synthetic(self):
        for name in ("facility-context.json", "subsection3-context.json"):
            path = self.root / name; context = json.loads(path.read_text())
            context["source_kind"] = "synthetic_cpu_diagnostic"; write(path, context)
        path = self.root / "body-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows: row["source_kind"] = "synthetic_cpu_diagnostic"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        result = measure(self.root, allow_diagnostic=True)
        self.assertEqual(result["source_kind"], "synthetic_cpu_diagnostic")
        self.assertFalse(result["legal_verdict_claimed"])


if __name__ == "__main__":
    unittest.main()
