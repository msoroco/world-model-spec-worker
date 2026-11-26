"""Synthetic CPU proof of saved door joins; no physical or legal acceptance."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from finalize import finalize


ASSIGNMENT = "training__C228817__NRS-484B-153-3__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(root, close, kind):
    root.mkdir(parents=True)
    number = (1 if close == 212 else 2) + (2 if kind == "cargo" else 0)
    case = ASSIGNMENT + "__probe_" + str(number)
    config = json.loads(Path(__file__).with_name(
        "config-probe-" + str(number) + ".json").read_text())
    write(root / "config.json", config)
    write(root / "original-map.json", {"map_name": "Town03"})
    write(root / "original-road.json", {"map_name": "Town03", "door_side": "left",
        "passing_side": "left"})
    write(root / "original-transfer.json", {"kind": kind, "frame": 200,
        "cargo_actor_id": "planned-cargo" if kind == "cargo" else None})
    sources = {name: {"path": "synthetic fixture only", "sha256":
        digest(root / ("original-" + name + ".json"))} for name in ("map", "road", "transfer")}
    write(root / "original-scene-review.json", {"source_kind": "source_bound_native_setup",
        "case_id": case, "sources": sources})
    mapping = []
    actors = []
    for i in range(600):
        mapping.append({"video_frame": i, "carla_frame": 1000 + i,
                        "native_frame": 1000 + i, "time_s": i / 20,
                        "native_elapsed_s": 12 + i / 20})
        actors.append({"video_frame": i, "native_frame": 1000 + i,
            "native_elapsed_s": 12 + i / 20, "driver_actor_id": 1,
            "passing_actor_id": 2, "pedestrian_actor_id": 3,
            "cargo_actor_id": 4 if kind == "cargo" else None,
            "ego_speed_mps": 0.0, "passing_lateral_offset_m": 2.0,
            "door_state_observed": None, "occupancy_delta_observed": None,
            "requested": {"door_command": "open" if 100 <= i < close else "closed"}})
    for filename, data in (("video_frames.jsonl", mapping), ("native-door-trace.jsonl", actors)):
        (root / filename).write_text("".join(json.dumps(row) + "\n" for row in data))
    (root / "trace.jsonl").write_text("".join(json.dumps({
        "frame": 1000 + i, "time_s": i / 20,
        "position": {"x": 0, "y": 0, "z": 0},
        "heading_deg": 0, "speed_mps": 0}) + "\n" for i in range(600)))
    video = root / "overview.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "lavfi", "-i", "color=c=blue:s=16x16:r=20", "-frames:v", "600",
        "-c:v", "ffv1", str(video)], check=True, timeout=120)
    for name in CAMERAS[1:]:
        shutil.copyfile(video, root / (name + ".mkv"))
    observations = [{"video_frame": i, "door_open": 100 <= i < close,
        "source_camera": "overview", "pixel_box_xyxy": [1, 1, 8, 8]}
        for i in range(600)]
    review = {"format": "c228817-door-pixel-review-v1", "case_id": case,
        "observed_traffic_side": "left", "observed_door_side": "left",
        "camera_sha256": {name: digest(root / (name + ".mkv")) for name in CAMERAS},
        "door_observations": observations,
        "transfer_events": [{"kind": kind, "video_frame": 200,
            "source_camera": "overview", "pixel_box_xyxy": [1, 1, 8, 8],
            **({"cargo_actor_id_observed": 4} if kind == "cargo"
               else {"occupancy_delta_observed": 1})}]}
    write(root / "door-pixel-review.json", review)
    return review


def reject(root, review, label, mutate, expected):
    changed = copy.deepcopy(review)
    mutate(changed)
    write(root / "door-pixel-review.json", changed)
    try:
        finalize(root, root / (label + ".json"))
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError((label, str(error))) from error
        return label
    raise AssertionError("Saved source guard accepted " + label)


def main():
    base = (Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c228817-saved-fixture").resolve()
    base.mkdir(parents=True, exist_ok=True)
    positives, negatives = [], []
    for kind in ("passenger", "cargo"):
        for close in (212, 400):
            number = (1 if close == 212 else 2) + (2 if kind == "cargo" else 0)
            root = base / (kind + "-" + str(close))
            if root.exists():
                shutil.rmtree(root)
            review = make(root, close, kind)
            report = finalize(root, root / "analysis.json")
            assert report["measured"]["close_frame"] == close
            assert report["measured"]["open_duration_s"] == (close - 100) / 20
            assert report["measured"]["legal_necessity"] == "unresolved_requires_contextual_review"
            assert not report["physical_acceptance_claimed"]
            assert json.loads((root / "result.json").read_text())["measured_values"]["open_duration_s"] == (close - 100) / 20
            from batch_pipeline.carla import validate_attempt
            construction = json.loads(Path(__file__).with_name(
                "probe-" + str(number) + "-construction.json").read_text())
            checked = validate_attempt(root, {"case": {"case_id": report["case_id"],
                "variable_assignments": {}}, "cell": {"cell_id": "C228817"},
                "actor": "motor_vehicle_driver"}, construction,
                {"recorded_exit_code": 0}, {})
            assert checked["rebuild_required"] and checked["case_id"] == report["case_id"]
            positives.append({"case_id": report["case_id"], "close_frame": close,
                              "transfer_kind": kind,
                              "open_duration_s": report["measured"]["open_duration_s"]})
            (root / "analysis.json").unlink()
            (root / "result.json").unlink()
            negatives.append(reject(root, review, "command_only",
                lambda r: r.update(door_observations=[]), "reviewed door state"))
            negatives.append(reject(root, review, "stale_video",
                lambda r: r["camera_sha256"].update(overview="0" * 64),
                "different camera bytes"))
            if kind == "passenger":
                negatives.append(reject(root, review, "missing_occupancy",
                    lambda r: r["transfer_events"][0].pop("occupancy_delta_observed"),
                    "occupancy change"))
            else:
                negatives.append(reject(root, review, "missing_cargo_identity",
                    lambda r: r["transfer_events"][0].pop("cargo_actor_id_observed"),
                    "Cargo identity"))
            negatives.append(reject(root, review, "wrong_case",
                lambda r: r.update(case_id="different"), "another exact case"))
            negatives.append(reject(root, review, "pixel_oob",
                lambda r: r["door_observations"][0].update(pixel_box_xyxy=[1, 1, 100, 100]),
                "pixel box"))
            write(root / "door-pixel-review.json", review)
            missing = root / "door-pixel-review.json"
            missing.unlink()
            try:
                finalize(root, root / "missing-review.json")
            except ValueError as error:
                assert "Missing required source: door-pixel-review.json" in str(error)
                negatives.append("missing_review")
            else:
                raise AssertionError("Missing review accepted")
    return {"format": "c228817-synthetic-saved-proof-v1", "positives": positives,
            "negative_guards": negatives, "physical_verified": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
