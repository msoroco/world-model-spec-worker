import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit
from road_scene import surface_gap


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value) + "\n")


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self, root, case=None):
        attempt = root / "attempt"
        attempt.mkdir()
        case = case or ROOT.name + "__prompt_brake"
        policy = case.rsplit("__", 1)[-1]
        config = {"law_id": "NRS-484B-280-1c", "cell_id": "C398030",
                  "actor": "motor_vehicle_driver", "duration_s": 30,
                  "cameras": [], "case": {"response_policy": policy}}
        write(attempt / "config.json", config)
        scene = json.loads((ROOT / "scene.json").read_text())
        scene["response_policy"] = policy
        scene["case_id"] = case
        write(attempt / "scene.json", scene)
        (attempt / "map.xodr").write_text("<OpenDRIVE>diagnostic</OpenDRIVE>")
        site = {"format": "worker-school-setting-site", "cell_id": "C398030",
                "layout": "school_zone", "control": "school", "crossing_type": "school_zone",
                "school_designation_source": "original Native school traffic-sign objects",
                "map_source": {"path": "map.xodr", "sha256": sha(attempt / "map.xodr")},
                "school_boundary_markers": [
                    {"original_object_id": "diagnostic/11", "name": "School Zone Begin", "location_xy_m": [-15, 2]},
                    {"original_object_id": "diagnostic/12", "name": "School Zone End", "location_xy_m": [15, 2]}],
                "ego_start_xy_m": scene["ego_start_xy_m"],
                "ego_end_xy_m": scene["ego_end_xy_m"],
                "original_road_id": 3, "original_lane_id": 1, "original_lane_width_m": 4,
                "ego_spawn_yaw_deg": 0,
                "lane_route_samples": [
                    {"requested_x_m": x, "center_xy_m": [x, 0], "yaw_deg": 0,
                     "road_id": 3, "lane_id": 1, "width_m": 4}
                    for x in range(-30, 31, 5)],
                "pedestrian_start_xy_m": scene["pedestrian_start_xy_m"],
                "pedestrian_end_xy_m": scene["pedestrian_end_xy_m"]}
        write(attempt / "school-site.json", site)
        history, trace, frames = [], [], []
        for i in range(9):
            frame, time_s = 100 + i, i / 20
            ego, ped = body(-12 + i, 0), body(0, 3.0)
            history.append({"frame": frame, "time_s": time_s,
                "ego_body_vertices_m": ego, "pedestrian_body_vertices_m": ped,
                "ego_speed_mps": 4, "ego_brake": int(i >= (2 if policy == "prompt_brake" else 5)),
                "pedestrian_class_source": "original diagnostic blueprint",
                "driver_control_source": "original diagnostic scripted controller",
                "pedestrian_class": "pedestrian", "ego_class": "motor_vehicle",
                "driver_observation_event": {"source": "original_driver_input", "observed": True}
                    if i >= 2 else None,
                "surface_gap_m": surface_gap(ego, ped), "contact_event": False})
            trace.append({"frame": frame, "time_s": time_s, "position_m": [-12 + i, 0, 0]})
            frames.append({"video_frame": i, "carla_frame": frame, "time_s": time_s})
        for name, values in (("encounter-history.jsonl", history),
                             ("trace.jsonl", trace), ("video_frames.jsonl", frames)):
            (attempt / name).write_text("".join(json.dumps(value) + "\n" for value in values))
        write(attempt / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(attempt / name)}
                                            for name in ("encounter-history.jsonl", "school-site.json", "map.xodr",
                                                         "video_frames.jsonl")})
        write(attempt / "result.json", {"case_id": case, "setup_confirmed": True,
                                        "behavior_attempted": True, "maneuver_completed": True})
        names = (*("encounter-history.jsonl", "school-site.json", "map.xodr", "trace.jsonl",
                   "video_frames.jsonl", "acquisition.json", "config.json", "scene.json"),)
        write(attempt / "capture-seal.json", {"events": ["capture_finished", "encoders_closed", "restoration_verified"],
              "sources": {name: sha(attempt / name) for name in names}})
        write(attempt / "native-exit.json", {"event": "native_exit",
                                             "capture_seal_sha256": sha(attempt / "capture-seal.json")})
        write(attempt / "owner-release.json", {"event": "owner_released", "operator_attested": True,
                                                "native_exit_sha256": sha(attempt / "native-exit.json")})
        analysis = root / "analysis"; analysis.mkdir()
        (analysis / "raw.mkv").write_bytes(b"diagnostic-only")
        saved = root / "saved-result.json"; write(saved, {"case_id": case})
        processing = root / "processing.json"
        write(processing, {"format": "worker-saved-processing", "passed": True,
                           "recorded_only": True, "result": str(saved), "result_sha256": sha(saved),
                           "analysis_directory": str(analysis)})
        decode = root / "decode.json"; write(decode, {"diagnostic": True})
        return attempt, processing, decode, case

    def test_positive_and_stale_source_rejection(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            attempt, processing, decode, case = self.fixture(Path(temp))
            receipt = audit(attempt, processing, decode, case, media_verify=lambda *a, **k: True)
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["measurement"]["first_brake"]["frame"], 102)
            with (attempt / "encounter-history.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "sealed original missing or changed"):
                audit(attempt, processing, decode, case, media_verify=lambda *a, **k: True)

    def test_missing_driver_input_and_media_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            attempt, processing, decode, case = self.fixture(Path(temp))
            rows = [json.loads(line) for line in (attempt / "encounter-history.jsonl").read_text().splitlines()]
            for row in rows:
                row["driver_observation_event"] = None
            (attempt / "encounter-history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            acquisition = json.loads((attempt / "acquisition.json").read_text())
            acquisition["encounter-history.jsonl"]["sha256"] = sha(attempt / "encounter-history.jsonl")
            write(attempt / "acquisition.json", acquisition)
            seal = json.loads((attempt / "capture-seal.json").read_text())
            seal["sources"]["encounter-history.jsonl"] = sha(attempt / "encounter-history.jsonl")
            seal["sources"]["acquisition.json"] = sha(attempt / "acquisition.json")
            write(attempt / "capture-seal.json", seal)
            write(attempt / "native-exit.json", {"event": "native_exit",
                                                 "capture_seal_sha256": sha(attempt / "capture-seal.json")})
            write(attempt / "owner-release.json", {"event": "owner_released", "operator_attested": True,
                                                    "native_exit_sha256": sha(attempt / "native-exit.json")})
            with self.assertRaisesRegex(ValueError, "input event absent"):
                audit(attempt, processing, decode, case, media_verify=lambda *a, **k: True)


if __name__ == "__main__":
    unittest.main()
