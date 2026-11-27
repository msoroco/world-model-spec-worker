"""Exercise exact selected saved-source joins with synthetic textual inputs."""
import json
import tempfile
from pathlib import Path

from saved_shoulder import join

ROOT = Path(__file__).resolve().parent.parent


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def write_rows(path, values):
    path.write_text("".join(json.dumps(value) + "\n" for value in values))


def fixture(folder, config):
    survey = {"source_kind": "synthetic_native_sample", "map_name": "synthetic-map",
              "highway_identity_source": "synthetic-map", "adjacent_paved_shoulder_source": "synthetic-map",
              "passing_lane_source": "synthetic-lane", "passing_traffic_side": "left",
              "lighting_hours_source": "synthetic-clock", "civil_time_source": "synthetic-clock",
              "ambient_reveal_protocol_source": "synthetic-optics",
              "front_lamp_protocol_source": "synthetic-optics",
              "rear_lamp_protocol_source": "synthetic-optics",
              "optical_target_kind": config["optical_target_kind"],
              "target_distance_ft": config["target_distance_ft"]}
    optics = {"source_kind": "synthetic_native_sample",
              "camera_sources": ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                                 "driver_reference.mkv"],
              "probes": {key: {"estimated_distance_ft": value,
                               "uncertainty_ft": .1, "method_source": "synthetic-method",
                               "pixel_evidence_source": "synthetic-pixels"}
                         for key, value in (("ambient_reveal", 1000),
                                            ("front_white_or_amber", 500),
                                            ("rear_red", 500))}}
    if config["optical_target_kind"] != "none":
        optics["probes"][config["optical_target_kind"]]["estimated_distance_ft"] = \
            config["target_distance_ft"]
    displayed = config["lamp_command"] == "display"
    trace = [{"source_kind": "synthetic_native_sample", "frame": i,
              "native_frame": 1500 + i, "video_frame": i, "time_s": i / 20,
              "ego_speed_mps": 0, "position_commanded": displayed,
              "low_beam_commanded": displayed, "passing_traffic_side": "left"}
             for i in range(600)]
    mapping = [{"native_frame": 1500 + i, "carla_frame": 1500 + i,
                "video_frame": i, "time_s": i / 20} for i in range(600)]
    write_json(folder / "shoulder_lighting_survey.json", survey)
    write_json(folder / "optical_measurements.json", optics)
    write_rows(folder / "shoulder-lamp-trace.jsonl", trace)
    write_rows(folder / "video_frames.jsonl", mapping)


def main():
    manifest = json.loads((ROOT / "selected-shoulder-draft-manifest.json").read_text())
    checks = {}
    for case in manifest["cases"]:
        path = ROOT / case["construction"]
        construction = json.loads(path.read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            fixture(folder, config)
            out = join(folder, config, allow_fixture=True)
            assert out["frames"] == 600 and not out["legal_verdict_claimed"]
            assert len(out["position_command_omission_frames"]) == \
                (0 if config["lamp_command"] == "display" else 600)
            checks[case["case_id"].split("__")[-1]] = {
                "joined_frames": out["frames"],
                "position_omissions": len(out["position_command_omission_frames"]),
                "target_relation": out["optical_brackets"].get(
                    config["optical_target_kind"], {}).get("threshold_relation")}
            if case is manifest["cases"][0]:
                negatives = {}
                for filename in ("shoulder_lighting_survey.json", "optical_measurements.json",
                                 "shoulder-lamp-trace.jsonl", "video_frames.jsonl"):
                    old = (folder / filename).read_text()
                    (folder / filename).unlink()
                    try:
                        join(folder, config, allow_fixture=True)
                    except ValueError as error:
                        negatives[filename] = str(error)
                    else:
                        raise AssertionError("Missing source accepted: " + filename)
                    (folder / filename).write_text(old)
                checks["missing_source_rejections"] = negatives
    print(json.dumps({"cases": checks, "original_native_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
