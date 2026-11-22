"""Saved finalizer rejects broken original-source joins before deriving a result."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import build_report

HERE = Path(__file__).resolve().parents[1]


class SavedAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        case = HERE/"cases"/"roadway_walk"
        for source, name in ((case/"scene.json", "scene.json"),
                             (case/"config.json", "config.json"),
                             (HERE/"candidate-corridor.xodr", "candidate-corridor.xodr")):
            shutil.copyfile(source, self.root/name)
        scene = json.loads((self.root/"scene.json").read_text())
        bodies = [json.loads(line) for line in
                  (case/"diagnostic-body-history.jsonl").read_text().splitlines()[:5]]
        def write_rows(name, values):
            (self.root/name).write_text("".join(json.dumps(value)+"\n" for value in values))
        write_rows("walker-body-history.jsonl", bodies)
        write_rows("trace.jsonl", [{"frame": b["frame"], "time_s": b["time_s"],
                 "position_m": [sum(p[0] for p in b["body_xy_m"])/4, 1.5, 0]}
                 for b in bodies])
        write_rows("video_frames.jsonl", [{"video_frame": i, "carla_frame": i,
                                           "time_s": b["time_s"]}
                                           for i, b in enumerate(bodies)])
        camera_names = ("overview", "approach", "reference_corner", "driver_reference")
        write_rows("camera-frame-joins.jsonl", [{"case_id": scene["case_id"],
                    "frame": i, "time_s": b["time_s"],
                    "cameras": {name: {"frame": i} for name in camera_names}}
                    for i, b in enumerate(bodies)])
        for name in camera_names:
            (self.root/(name+".mkv")).write_bytes(b"diagnostic-video-placeholder")
        (self.root/"acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}))

    def test_measures_saved_whole_body_without_legal_verdict(self):
        report, _, _, _, _ = build_report(self.root)
        measured = report["measurements"]["pedestrian_full_body_band_occupancy"]["value"]
        self.assertEqual(measured["frames"], 5)
        self.assertTrue(measured["all_body_inside_route_band"])
        self.assertFalse(report["legal_verdict_claimed"])

    def test_missing_body_source_fails(self):
        (self.root/"walker-body-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: walker-body-history.jsonl"):
            build_report(self.root)

    def test_stale_camera_join_fails(self):
        path = self.root/"camera-frame-joins.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[2]["cameras"]["approach"]["frame"] = 1
        path.write_text("".join(json.dumps(row)+"\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "four original camera frame joins missing"):
            build_report(self.root)


if __name__ == "__main__":
    unittest.main()
