"""A 900-frame saved fixture exercises the actual selected analyzer entrypoint."""
import json
import hashlib
from pathlib import Path
import subprocess
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

    def test_full_video_native_validation_remains_diagnostic(self):
        from batch_pipeline.carla import validate_attempt
        trace_path = self.root / "trace.jsonl"
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
        for row in trace:
            row.update(heading_deg=0.0, velocity_mps=[row["speed_mps"], 0, 0],
                       position={"x": row["position_m"][0], "y": 0, "z": 0})
        trace_path.write_text("".join(json.dumps(row) + "\n" for row in trace))
        saved = json.loads((self.root / "saved-manifest.json").read_text())
        for name, view in saved["camera_views"].items():
            video = self.root / (name + ".mkv")
            video.unlink()
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", "color=c=black:s=16x16:r=20",
                            "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact", str(video)],
                           check=True)
            view["source"]["sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
        (self.root / "saved-manifest.json").write_text(json.dumps(saved) + "\n")
        analysis.analyze(self.root)
        construction = json.loads((ROOT / "construction-two_cycles_clear.json").read_text())
        proposal = json.loads((ROOT / "proposals/cases.json").read_text())
        case = next(row for row in proposal["cases"] if row["case_id"].endswith("__two_cycles_clear"))
        validated = validate_attempt(self.root,
                                     {"case": case, "cell": {"cell_id": "C111125"},
                                      "actor": "motorcycle_or_moped_operator"},
                                     construction, {"recorded_exit_code": 0}, {}, source_audits={})
        self.assertTrue(validated["rebuild_required"])
        self.assertFalse(validated["situation_confirmed"])
        self.assertEqual(len(validated["video_references"]), 4)
        (self.root / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or out-of-attempt recording"):
            validate_attempt(self.root,
                             {"case": case, "cell": {"cell_id": "C111125"},
                              "actor": "motorcycle_or_moped_operator"},
                             construction, {"recorded_exit_code": 0}, {}, source_audits={})


if __name__ == "__main__":
    unittest.main()
