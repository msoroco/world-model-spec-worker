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


def make(root, close):
    root.mkdir(parents=True)
    case = ASSIGNMENT + "__probe_" + ("1" if close == 212 else "2")
    write(root / "config.json", {"case_id": case, "duration_frames": 600, "rate_hz": 20})
    write(root / "original-map.json", {"map_name": "Town03"})
    write(root / "original-road.json", {"map_name": "Town03", "door_side": "left",
        "passing_side": "left"})
    write(root / "original-transfer.json", {"kind": "passenger", "frame": 200})
    sources = {name: {"path": "synthetic fixture only", "sha256":
        digest(root / ("original-" + name + ".json"))} for name in ("map", "road", "transfer")}
    write(root / "original-scene-review.json", {"source_kind": "source_bound_native_setup",
        "case_id": case, "sources": sources})
    mapping = []
    actors = []
    for i in range(600):
        mapping.append({"video_frame": i, "native_frame": 1000 + i,
                        "native_elapsed_s": 12 + i / 20})
        actors.append({"video_frame": i, "native_frame": 1000 + i,
            "native_elapsed_s": 12 + i / 20, "driver_actor_id": 1,
            "passing_actor_id": 2, "pedestrian_actor_id": 3,
            "ego_speed_mps": 0.0, "passing_lateral_offset_m": 2.0,
            "door_state_observed": None, "occupancy_delta_observed": None,
            "requested": {"door_command": "open" if 100 <= i < close else "closed"}})
    for filename, data in (("video_frames.jsonl", mapping), ("native-door-trace.jsonl", actors)):
        (root / filename).write_text("".join(json.dumps(row) + "\n" for row in data))
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
        "transfer_events": [{"kind": "passenger", "video_frame": 200,
            "source_camera": "overview", "pixel_box_xyxy": [1, 1, 8, 8],
            "occupancy_delta_observed": 1}]}
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
    base = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c228817-saved-fixture"
    base.mkdir(parents=True, exist_ok=True)
    positives, negatives = [], []
    for close in (212, 400):
        root = base / str(close)
        if root.exists():
            shutil.rmtree(root)
        review = make(root, close)
        report = finalize(root, root / "analysis.json")
        assert report["measured"]["close_frame"] == close
        assert report["measured"]["open_duration_s"] == (close - 100) / 20
        assert report["measured"]["legal_necessity"] == "unresolved_requires_contextual_review"
        assert not report["physical_acceptance_claimed"]
        positives.append({"case_id": report["case_id"], "close_frame": close,
                          "open_duration_s": report["measured"]["open_duration_s"]})
        (root / "analysis.json").unlink()
        negatives.append(reject(root, review, "command_only",
            lambda r: r.update(door_observations=[]), "reviewed door state"))
        negatives.append(reject(root, review, "stale_video",
            lambda r: r["camera_sha256"].update(overview="0" * 64),
            "different camera bytes"))
        negatives.append(reject(root, review, "missing_occupancy",
            lambda r: r["transfer_events"][0].pop("occupancy_delta_observed"),
            "occupancy change"))
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
