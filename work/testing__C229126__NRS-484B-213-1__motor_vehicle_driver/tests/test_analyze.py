import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analyze", ROOT / "analyze.py")
import sys
sys.path.insert(0, str(ROOT))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from test_pass_measure import packet as sample_packet


class SavedAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "reviewed-sources").mkdir()
        (self.root / "reviewed-sources/map.source").write_text("map")
        (self.root / "reviewed-sources/centerline.source").write_text("line")
        source = sample_packet()
        road = source["road"]
        road["centerline_source_sha256"] = module.sha(self.root / "reviewed-sources/centerline.source")
        road["lanes"] = [{"lane_id": "forward", "direction": 1},
                         {"lane_id": "reverse", "direction": -1}]
        (self.root / "road-context.json").write_text(json.dumps(road))
        desc = {"purpose": "source-bound pass evidence"}
        (self.root / "native-result.json").write_text(json.dumps({"recording_description": desc}))
        (self.root / "config.json").write_text(json.dumps({"selected_case_id": "assignment__clear_free_complete",
                                                           "duration_s": .2,
                                                           "case": {"recording_description": desc}}))
        rows = []
        maps = []
        for index, frame in enumerate(source["frames"]):
            frame["carla_frame"] = 100 + index
            frame["time_s"] = index*.05
            for actor_id, actor in enumerate(frame["actors"].values(), 1):
                actor["actor_id"] = actor_id
                actor["lateral_m"] = 0
            frame["actors"]["ego"]["rear_station_m"] = frame["actors"]["ego"]["station_m"]-2
            frame["actors"]["overtaken"]["front_station_m"] = 22
            rows.append(json.dumps(frame))
            maps.append(json.dumps({"carla_frame": 100+index, "time_s": index*.05}))
        (self.root / "pass-history.jsonl").write_text("\n".join(rows) + "\n")
        (self.root / "video_frames.jsonl").write_text("\n".join(maps) + "\n")

    def test_positive_all_statutory_components(self):
        report, _ = module.analyze(self.root)
        self.assertEqual(set(report["measurements"]), {m.__name__ for m in module.METHODS})
        self.assertEqual(report["measurements"]["measure_completion"]["value"]["pass_and_return_frame"], 3)
        self.assertFalse(report["physical_acceptance_claimed"])

    def test_missing_original_history_rejected(self):
        (self.root / "pass-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: pass-history"):
            module.analyze(self.root)

    def test_missing_original_frame_rejected(self):
        rows = (self.root / "pass-history.jsonl").read_text().splitlines()
        broken = json.loads(rows[2]); broken["carla_frame"] = 999
        rows[2] = json.dumps(broken)
        (self.root / "pass-history.jsonl").write_text("\n".join(rows) + "\n")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            module.analyze(self.root)

    def test_saved_channel_streams_keep_original_times(self):
        evidence = module.write_channels(self.root, {"channels": [
            {"name": "ego_target_oncoming_body_history", "unit": "structured original-source record"},
            {"name": "oncoming_forward_distance", "unit": "structured original-source record"}]})
        self.assertEqual(len(evidence), 2)
        samples = module.rows(self.root / evidence[1]["reference"])
        for actual, expected in zip([r["time_s"] for r in samples], [0, .05, .1, .15]):
            self.assertAlmostEqual(actual, expected)
        self.assertIsInstance(samples[1]["value"]["forward_station_gap_m"], (int, float))


if __name__ == "__main__": unittest.main()
