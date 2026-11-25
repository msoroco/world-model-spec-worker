"""A 900-frame saved fixture exercises the actual selected analyzer entrypoint."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))
import analysis
import original_capture
from worker_exchange.measurement_contract import verify_report
import test_original_capture as capture_fixture


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        fixture = capture_fixture.OriginalCaptureTest("test_full_capture_seals_original_trace_for_existing_measurement")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.site = fixture.site
        self.site["case_id"] = ROOT.name + "__two_cycles_clear"
        self.site["diagnostic_fixture"] = True
        (self.root / "native-site.json").write_text(json.dumps(self.site) + "\n")
        rows = fixture.rows()
        receipt = original_capture.capture_original(self.site, self.root, capture_fixture.Adapter(rows),
                                                     self.root / "original-events.json",
                                                     diagnostic_fixture=True)
        refs = self.site["original_sources"]
        sources = {"original_events": receipt["event_ref"],
                   "map": refs["map_ref"], "route": refs["route_ref"],
                   "signal": refs["signal_ref"], "stop_reference": refs["stop_ref"],
                   "crosswalk": refs["crosswalk_ref"], "cause": refs["cause_ref"]}
        views = {}
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            views[name] = {"source": capture_fixture.source(self.root, name + ".mkv", "diagnostic camera inventory"),
                           "decoded_frames": 900, "fps": 20, "width": 16, "height": 16,
                           "first_original_frame": 0, "last_original_frame": 899}
        saved = {"assignment_id": ROOT.name, "case_id": self.site["case_id"],
                 "law_id": "NRS-484B-307-9b", "actor": "motorcycle_or_moped_operator",
                 "fps": 20, "duration_frames": 900, "sources": sources,
                 "official_head_id": "head-17", "actor_id": "ego-1",
                 "camera_views": views, "pixel_review_status": "pending"}
        (self.root / "saved-manifest.json").write_text(json.dumps(saved) + "\n")
        (self.root / "media-receipt.json").write_text("{}\n")
        (self.root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        construction = json.loads((ROOT / "construction-two_cycles_clear.json").read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        (self.root / "config.json").write_text(json.dumps(config) + "\n")
        self.mapping = [{"video_frame": i, "carla_frame": row["frame"],
                         "time_s": row["time_s"]} for i, row in enumerate(rows)]
        (self.root / "trace.jsonl").write_text("".join(json.dumps({
            "frame": row["frame"], "time_s": row["time_s"],
            "position_m": [row["ego_front_station_m"], 0, 0],
            "speed_mps": row["speed_mps"]}) + "\n" for row in rows))
        self._write_map()

    def _write_map(self):
        (self.root / "video_frames.jsonl").write_text("".join(
            json.dumps(row) + "\n" for row in self.mapping))

    def test_saved_analyzer_emits_canonical_result_from_originals(self):
        report = analysis.analyze(self.root)
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(report["measurements"]["complete_cycles"]["value"]["full_cycles_after_stop"], 2)
        self.assertEqual(len(result["recording_evidence"]), 8)
        self.assertTrue(all(check["matched"] for check in result["target_checks"]))
        self.assertTrue(result["diagnostic_fixture"])
        self.assertFalse(result["physical_acceptance_claimed"])
        contract = json.loads((ROOT / "contracts/two_cycles_clear.json").read_text())
        self.assertEqual(len(verify_report(contract, report, self.root)), 7)

    def test_saved_analyzer_rejects_frame_join_change(self):
        self.mapping[100]["time_s"] += 0.1
        self._write_map()
        with self.assertRaisesRegex(ValueError, "event/camera frame join"):
            analysis.analyze(self.root)
        self.assertFalse((self.root / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
