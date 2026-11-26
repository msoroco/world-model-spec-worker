"""Independent saved-source audit for exact adjacent-lane delivery attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SUFFIXES = {"both_stationary", "left_moving", "right_moving", "both_moving",
            "within_left", "police_on_duty", "police_off_duty", "moped_between"}
PREFIX = "testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator__"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def video(path, width, height):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate,codec_name",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    require(len(streams) == 1, "Camera video needs one stream")
    stream = streams[0]
    require(stream["codec_name"] == "ffv1" and
            (stream["width"], stream["height"]) == (width, height) and
            stream["r_frame_rate"] == "20/1" and int(stream["nb_read_frames"]) == 900,
            "Camera source codec, size, rate or decoded frame count differs")
    return sha(path)


def audit(attempt, case_id, require_original=False):
    root = Path(attempt).resolve()
    require(case_id.startswith(PREFIX) and case_id[len(PREFIX):] in SUFFIXES,
            "Foreign exact case")
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    require(config["selected_case_id"] == case_id and config["duration_s"] == 45 and
            config["rate_hz"] == 20, "Exact attempt identity or 900-frame profile differs")
    original = (root / "acquisition.json").is_file()
    if require_original and not original:
        raise ValueError("Diagnostic source cannot satisfy original Native delivery")
    if original:
        provenance = json.loads((root / "acquisition-provenance.json").read_text())
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False,
                "Original Native provenance missing")
        acquisition = json.loads((root / "acquisition.json").read_text())
    else:
        marker = json.loads((root / "diagnostic-source-note.json").read_text())
        require(marker.get("source_kind") == "synthetic_diagnostic_fixture" and
                marker.get("case_id") == case_id, "Diagnostic provenance differs")
        acquisition = {}
    source_names = ("lane-split-history.jsonl", "lane-split-scene.json",
                    "trace.jsonl", "video_frames.jsonl", *[name + ".mkv" for name in CAMERAS])
    seals = {}
    for name in source_names:
        path = root / name
        require(path.is_file() and not path.is_symlink(), "Missing exact saved source: " + name)
        seals[name] = sha(path)
        if original:
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == seals[name],
                    "Original Native source seal differs: " + name)
    history, trace, mapping = [rows(root / name) for name in
                               ("lane-split-history.jsonl", "trace.jsonl", "video_frames.jsonl")]
    require(len(history) == len(trace) == len(mapping) == 900,
            "Incomplete original frame or camera map history")
    frames = [item["frame"] for item in history]
    require(frames == list(range(frames[0], frames[0] + 900)),
            "Original frames not consecutive")
    for h, t, m in zip(history, trace, mapping):
        require(h["frame"] == t["frame"] == m["carla_frame"] and
                h["time_s"] == t["time_s"] == m["time_s"],
                "Original actor, telemetry and video frame join differs")
        require(set(h["actors"]) == {"ego", "left_occupant", "right_occupant"} and
                len({a["actor_id"] for a in h["actors"].values()}) == 3,
                "Original three-participant identity missing")
    scene = json.loads((root / "lane-split-scene.json").read_text())
    require(scene["case_id"] == case_id and
            scene["operator_status"] == config["case"]["operator_status"] and
            scene["performance_of_duty"] == config["case"]["performance_of_duty"] and
            scene["ego_vehicle_class"] == config["case"]["vehicle_class"] and
            all(scene.get(key) for key in ("classification_source_sha256",
                                             "operator_identity_source_sha256",
                                             "police_status_source_sha256",
                                             "performance_of_duty_source_sha256")),
            "Exact operator, chapter class or duty context missing")
    cameras = {name: video(root / (name + ".mkv"), *dimensions)
               for name, dimensions in CAMERAS.items()}
    pixel_review = False
    if original:
        review_path = root / "independent-pixel-review.json"
        require(review_path.is_file(), "Original pixels await independent review")
        review = json.loads(review_path.read_text())
        require(review.get("case_id") == case_id and
                review.get("frame_map_sha256") == seals["video_frames.jsonl"] and
                review.get("camera_sha256") == cameras and
                review.get("status") == "reviewed" and review.get("reviewer"),
                "Independent original pixel review changed or incomplete")
        pixel_review = True
    native_result = json.loads((root / "result.json").read_text())
    require(native_result.get("case_id") == case_id and
            native_result.get("diagnostic_fixture") is (not original),
            "Saved Native result identity or provenance differs")
    completion = bool(original and native_result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met" and
                      native_result.get("maneuver_completed") is True)
    return {"format": "c145696-source-audit", "case_id": case_id,
            "native_source": original, "all_participants": True,
            "time_join": True, "full_video_decode": True,
            "actual_pixels": pixel_review, "physical_completion": completion,
            "original_frames": 900, "source_sha256": seals,
            "camera_sha256": cameras}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--require-original", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.require_original), sort_keys=True))


if __name__ == "__main__":
    main()
