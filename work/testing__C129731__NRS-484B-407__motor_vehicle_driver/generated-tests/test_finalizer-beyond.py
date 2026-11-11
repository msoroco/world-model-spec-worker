import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE.parents[1]/"runtime"/"scenario_pipeline"))
from finalizer import analyze_sources
from traffic_spec_adapter.visibility import CONVENTION


def visibility():
    return {"visibility_criterion": "any_of_nine_body_samples",
            "distance_convention": CONVENTION, "eye_height_m": 1.4,
            "scan_step_m": 10., "horizon_tolerance_m": .25, "probe_distance_m": 152.4,
            "ego_body_samples_m": [[float(i), 0., 1.] for i in range(9)],
            "required_lane_ids": [-1, 1],
            "approaches": [
                {"lane_id": -1, "any_sample_clear_at_probe": True,
                 "any_body_sight_horizon": {"bound": "first_sampled_occlusion",
                                            "bracket_m": [160., 160.125]}},
                {"lane_id": 1, "any_sample_clear_at_probe": True,
                 "any_body_sight_horizon": {"bound": "at_least", "distance_m": 230.}}]}


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row)+"\n" for row in rows))


class SavedSourceTests(unittest.TestCase):
    def test_original_motion_ray_and_frame_joins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("config.json", "diagnostic-site-beyond.json"):
                shutil.copyfile(PACKAGE/name, root/name)
            mapping, motion, trace, evidence, turns = [], [], [], [], []
            source_sha = json.loads((root/"config.json").read_text())["site_source"]["sha256"]
            site = json.loads((root/"diagnostic-site-beyond.json").read_text())
            (root/"curve_context.json").write_text(json.dumps({
                "site_source_sha256": source_sha, "feature": site["feature"],
                "turn_site_xyz_m": site["turn_site_xyz_m"],
                "incoming_lanes": site["incoming_lanes"],
                "visibility_proxy_only": True}))
            for i in range(1100):
                frame, time = i+1000, i/20
                mapping.append({"video_frame": i, "native_frame": frame, "time_s": time})
                ego = {"location_xyz_m": [0, 0, 0], "yaw_deg": 0,
                       "velocity_xyz_mps": [0, 0, 0], "road_lane": [10, -1]}
                approaches = {name: {"location_xyz_m": [(-160 if name == "approach_a" else 160), 0, 0],
                                      "yaw_deg": (0 if name == "approach_a" else 180),
                                      "velocity_xyz_mps": [1, 0, 0],
                                      "road_lane": [10, (-1 if name == "approach_a" else 1)]}
                              for name in ("approach_a", "approach_b")}
                motion.append({"video_frame": i, "native_frame": frame,
                               "site_source_sha256": source_sha,
                               "ego": ego, "approaches": approaches})
                trace.append({"frame": frame, "time_s": time})
                evidence.append({"original_frame": frame, "recording_time_s": time,
                                 "visibility": visibility()})
                turns.append({"frame": frame, "time_s": time,
                              "body_vertices_m": [[x, y, z] for x in (-1, 1)
                                                  for y in (-.8, .8) for z in (0, 1.5)],
                              "heading_deg": 0})
            write_rows(root/"video_frames.jsonl", mapping)
            write_rows(root/"motion_history.jsonl", motion)
            write_rows(root/"trace.jsonl", trace)
            write_rows(root/"capture/evidence.jsonl", evidence)
            write_rows(root/"turn_history.jsonl", turns)
            report = analyze_sources(root)
            self.assertEqual(report["turn_frame_sight"]["pinned_proxy_m"], 160.)
            self.assertEqual(report["turn_frame"], 1000)
            self.assertFalse(report["turn_frame_sight"]["actual_driver_eye_verified"])
            evidence[0].pop("visibility")
            write_rows(root/"capture/evidence.jsonl", evidence)
            with self.assertRaisesRegex(ValueError, "Missing original sight rays"):
                analyze_sources(root)
            evidence[0]["visibility"] = visibility()
            write_rows(root/"capture/evidence.jsonl", evidence)
            mapping[0]["native_frame"] += 1
            write_rows(root/"video_frames.jsonl", mapping)
            with self.assertRaisesRegex(ValueError, "Original frame/time join differs"):
                analyze_sources(root)


if __name__ == "__main__":
    unittest.main()
