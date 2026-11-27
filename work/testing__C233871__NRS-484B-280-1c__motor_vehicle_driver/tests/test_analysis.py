import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analysis", ROOT / "analysis.py")
import sys
sys.path.insert(0, str(ROOT))
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


class SavedAnalysisTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "map.xodr").write_text("<OpenDRIVE/>")
        site = {"format": "worker-on-road-site", "cell_id": "C233871",
                "layout": "road_without_sidewalk", "sidewalk_present": False,
                "map_source": {"path": "map.xodr", "sha256": analysis.sha(self.root / "map.xodr")},
                "road": {"lateral_bounds_m": [-3, 3], "classification_source": "original-map",
                         "edge_review_source": "original-map"},
                "ego_start_xy_m": [-30, 0], "ego_end_xy_m": [20, 0],
                "pedestrian_start_xy_m": [0, 1], "pedestrian_end_xy_m": [0, -1]}
        (self.root / "road-site.json").write_text(json.dumps(site) + "\n")
        self.history = []
        for index in range(9):
            ego, ped = body(-12 + index, 0), body(0, 1)
            self.history.append({"frame": 100 + index, "time_s": index * .05,
                                 "ego_body_vertices_m": ego, "pedestrian_body_vertices_m": ped,
                                 "ego_speed_mps": 4, "ego_brake": int(index >= 4),
                                 "pedestrian_class_source": "original-actor-blueprint",
                                 "driver_control_source": "original-driver-input",
                                 "pedestrian_class": "pedestrian", "ego_class": "motor_vehicle",
                                 "driver_observation_event": {"source": "original_driver_input", "observed": True}
                                     if index >= 2 else None,
                                 "surface_gap_m": max(0, -(ego[1][0])), "contact_event": False})
        self.write_rows()
        self.seal()

    def write_rows(self):
        (self.root / "encounter-history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in self.history))
        (self.root / "video_frames.jsonl").write_text("".join(
            json.dumps({"video_frame": i, "carla_frame": row["frame"],
                        "native_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
            for i, row in enumerate(self.history)))

    def seal(self):
        acquisition = {name: {"kind": "original_native", "sha256": analysis.sha(self.root / name)}
                       for name in analysis.REQUIRED}
        (self.root / "acquisition.json").write_text(json.dumps(acquisition) + "\n")

    def test_original_history_yields_observed_not_legal_measurements(self):
        value, _, _, _ = analysis.measure(self.root)
        self.assertEqual(value["first_observation"]["frame"], 102)
        self.assertEqual(value["first_brake"]["frame"], 104)
        self.assertAlmostEqual(value["observed_response_delay_s"], .1)
        self.assertEqual(value["legal_proper_caution_verdict"], "unresolved")

    def test_missing_driver_observation_does_not_claim_it(self):
        for row in self.history:
            row["driver_observation_event"] = None
        self.write_rows(); self.seal()
        value, _, _, _ = analysis.measure(self.root)
        self.assertIsNone(value["first_observation"])
        self.assertIsNone(value["observed_response_delay_s"])

    def test_rejects_stale_source_and_camera_join(self):
        (self.root / "map.xodr").write_text("changed")
        with self.assertRaisesRegex(ValueError, "stale"):
            analysis.measure(self.root)
        (self.root / "map.xodr").write_text("<OpenDRIVE/>")
        lines = (self.root / "video_frames.jsonl").read_text().splitlines()
        first = json.loads(lines[0]); first["carla_frame"] = -1
        lines[0] = json.dumps(first)
        (self.root / "video_frames.jsonl").write_text("\n".join(lines) + "\n")
        self.seal()
        with self.assertRaisesRegex(ValueError, "identities differ"):
            analysis.measure(self.root)


if __name__ == "__main__":
    unittest.main()
