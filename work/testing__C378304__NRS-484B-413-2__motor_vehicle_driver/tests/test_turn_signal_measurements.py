import importlib.util
import json
import hashlib
import tempfile
import unittest
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_finalizer import finalize_saved
spec = importlib.util.spec_from_file_location("turn_signal_measurements", Path(__file__).resolve().parents[1] / "turn_signal_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class TurnSignalTests(unittest.TestCase):
    def fixture(self, root, distance, district="business", interrupted=False):
        zone = root / "freight-zone-site-source.txt"
        zone.write_text("Synthetic zone source for CPU fixture; physical sign and district unverified.\n")
        context = {"native_map_id": "TownX", "approach_road_id": 1,
                   "approach_lane_id": -1, "outgoing_road_id": 2,
                   "outgoing_lane_id": -1, "native_route_source": "native-lane-links",
                   "district_source": "source-reviewed-map-context",
                   "freight_loading_zone_source": zone.name,
                   "freight_loading_zone_source_sha256": hashlib.sha256(zone.read_bytes()).hexdigest(),
                   "district_type": district, "turn_onset_frame": 104}
        (root / "route_context.json").write_text(json.dumps(context))
        x = [-1, 0, distance / 2, distance * .75, distance,
             distance + 1, distance + 2]
        indicators = [False, True, True, not interrupted, True, True, True]
        headings = [0, 0, 0, 0, -5, -25, -65]
        rows = [{"frame": 100+i, "time_s": 1+i*.05,
                 "ego_position_xy_m": [point, 0], "ego_speed_mps": 5,
                 "ego_heading_deg": headings[i],
                 "native_road_id": 1 if i < 6 else 2,
                 "native_lane_id": -1,
                 "ego_light_mask": 16 if indicators[i] else 0,
                 "right_indicator": indicators[i],
                 "ego_body_vertices_xy_m": [[point-1, -1], [point+1, -1],
                                              [point-1, 1], [point+1, 1]]}
                for i, point in enumerate(x)]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "drive_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_100_foot_below_at_above_and_300_foot_area(self):
        for distance, expected in ((30.47, False), (30.48, True), (30.49, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, distance)
                result = measure.analyze(root)
                self.assertAlmostEqual(result["turn_onset"]["continuous_right_signal_distance_m"], distance)
                self.assertEqual(result["observed_continuous_distance_meets_boundary"], expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, district="other")
            self.assertAlmostEqual(measure.analyze(root)["required_distance_m"], 91.44)

    def test_interruption_resets_distance_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, interrupted=True)
            result = measure.analyze(root)
            self.assertLess(result["turn_onset"]["continuous_right_signal_distance_m"], 30.48)
            self.fixture(root, 30.48)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[3]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_authored_onset_and_direction_must_match_source_course(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48)
            context = json.loads((root / "route_context.json").read_text())
            context["turn_onset_frame"] = 103
            (root / "route_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "disagrees"):
                measure.analyze(root)
            context["turn_onset_frame"] = 104
            (root / "route_context.json").write_text(json.dumps(context))
            rows = [json.loads(line) for line in (root / "drive_history.jsonl").read_text().splitlines()]
            for row in rows:
                row["ego_heading_deg"] = -row["ego_heading_deg"]
            (root / "drive_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "right-turn onset"):
                measure.analyze(root)

    def test_zone_source_and_native_light_mask_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48)
            (root / "freight-zone-site-source.txt").write_text("changed source\n")
            with self.assertRaisesRegex(ValueError, "bound source"):
                measure.analyze(root)
            self.fixture(root, 30.48)
            rows = [json.loads(line) for line in (root / "drive_history.jsonl").read_text().splitlines()]
            rows[2]["ego_light_mask"] = 0
            (root / "drive_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "light-mask"):
                measure.analyze(root)

    def test_saved_finalizer_derives_channels_and_preserves_unknown_physical_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48)
            folder = Path(__file__).resolve().parents[1]
            (root / "config.json").write_bytes((folder / "config.json").read_bytes())
            history = [json.loads(line) for line in (root / "drive_history.jsonl").read_text().splitlines()]
            (root / "trace.jsonl").write_text("".join(json.dumps({
                "frame": row["frame"], "time_s": row["time_s"]}) + "\n" for row in history))
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text('{"frame":100}\n')
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (name + ".mkv")).write_bytes(b"synthetic placeholder; decode tested separately")
            analysis = finalize_saved(root, root / "analysis.json")
            self.assertEqual(analysis["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
            self.assertFalse(analysis["physical_acceptance_claimed"])
            self.assertTrue((root / "channels/ego_turn_indicator.jsonl").is_file())
            self.assertTrue((root / "channels/path_distance.jsonl").is_file())
            self.assertEqual(json.loads((root / "result.json").read_text())["physical_acceptance_claimed"], False)


if __name__ == "__main__":
    unittest.main()
