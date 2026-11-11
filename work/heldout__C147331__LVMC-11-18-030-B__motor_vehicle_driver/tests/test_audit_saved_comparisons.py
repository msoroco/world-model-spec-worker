import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_saved_comparisons import digest, load_packet


CASE = "heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__within_marked_lane"


class SavedAuditTests(unittest.TestCase):
    def test_source_hash_and_result_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            version = Path(temporary)
            stage = version / "analysis"
            (stage / "capture").mkdir(parents=True)
            config = {"selected_case_id": CASE, "cameras": [{"name": "overview"}],
                      "duration_s": 8, "rate_hz": 20}
            (stage / "config.json").write_text(json.dumps(config))
            (stage / "capture/manifest.json").write_text(json.dumps({"map": "SyntheticTown"}))
            row = {"frame": 10, "lane": {"road_id": 7, "lane_id": 1,
                   "polygon_xy_m": [[0, 0], [1, 0], [1, 1], [0, 1]],
                   "lane_heading_xy": [1, 0], "left_marking": "Solid",
                   "right_marking": "Broken"}}
            source = stage / "marked_lane_sources.jsonl"
            source.write_text(json.dumps(row) + "\n")
            report = {"case_id": CASE, "measurements": {"lane_boundary_observation": {
                "sources": {"marked_lane_sources.jsonl": digest(source)},
                "value": {"frames": [{"frame": 10, "full_footprint_inside": True}],
                          "overtaken_id": None, "measured_order_reversal": False}}}}
            (stage / "analysis-report.json").write_text(json.dumps(report))
            result = stage / "result.json"
            result.write_text("{}")
            (version / "processing.json").write_text(json.dumps({"case_id": CASE,
                "missing_evidence": False, "originals_preserved": True,
                "result_sha256": digest(result)}))
            packet = load_packet(version, CASE)
            self.assertEqual(packet["case_id"], CASE)
            source.write_text(json.dumps(dict(row, frame=11)) + "\n")
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                load_packet(version, CASE)
            source.write_text(json.dumps(row) + "\n")
            result.write_text("{\"changed\":true}")
            with self.assertRaisesRegex(ValueError, "result hash differs"):
                load_packet(version, CASE)


if __name__ == "__main__":
    unittest.main()
