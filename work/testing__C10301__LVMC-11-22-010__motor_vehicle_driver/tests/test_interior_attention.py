import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from interior_attention import measure, sample

CASE = ROOT.name + "__attention_probe"
SENSOR = {"review_status": "reviewed", "observable": "original_eyes_off_road_duration_s",
          "sensor_id": "unit-test-sensor", "source_sha256": "a" * 64}


class Adapter:
    def read_interior(self, actor, snapshot, sensor_id):
        return {"source_kind": "original_native_interior", "case_id": CASE,
                "native_frame": snapshot.frame,
                "native_time_s": snapshot.timestamp.elapsed_seconds,
                "sensor_id": sensor_id, "sensor_source_sha256": SENSOR["source_sha256"],
                "eyes_off_road": snapshot.frame % 2 == 0,
                "native_verified": True}


class InteriorAttentionTests(unittest.TestCase):
    def rows(self):
        return [sample(Adapter(), object(), SimpleNamespace(frame=i,
                timestamp=SimpleNamespace(elapsed_seconds=i / 20)), CASE, SENSOR)
                for i in range(4)]

    def measure_rows(self, rows):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as temp:
            path = Path(temp) / "interior.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            return measure(path, CASE, expected_frames=4)

    def test_original_frame_measurement_has_no_legal_label(self):
        report = self.measure_rows(self.rows())
        self.assertEqual(report["original_eyes_off_road_duration_s"], .1)
        self.assertEqual(report["legal_judgment"], "unresolved")
        self.assertFalse(report["physical_acceptance_claimed"])

    def test_missing_review_or_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, "source-reviewed"):
            sample(Adapter(), object(), SimpleNamespace(frame=0,
                   timestamp=SimpleNamespace(elapsed_seconds=0)), CASE,
                   {**SENSOR, "review_status": "unreviewed"})
        rows = self.rows()
        rows[2]["sensor_id"] = "changed"
        with self.assertRaisesRegex(ValueError, "continuity"):
            self.measure_rows(rows)

    def test_missing_frame_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as temp:
            path = Path(temp) / "interior.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in self.rows()[:3]))
            with self.assertRaisesRegex(ValueError, "complete original"):
                measure(path, CASE, expected_frames=4)


if __name__ == "__main__":
    unittest.main()
