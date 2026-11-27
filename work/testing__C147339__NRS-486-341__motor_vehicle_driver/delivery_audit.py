"""Independent saved-source audit of one exact protected-lane attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


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
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


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
            "Camera source codec, size, rate or frame count differs")
    return sha(path)


def audit(attempt, case_id, require_original=False):
    root = Path(attempt).resolve()
    plan = json.loads((ROOT / "case-plan.json").read_text())
    require(case_id in {item["case_id"] for item in plan["cases"]}, "Foreign exact case")
    config = json.loads((root / "config.json").read_text())
    require(config["selected_case_id"] == case_id and config["duration_s"] == 45 and
            config["rate_hz"] == 20, "Exact attempt identity or profile differs")
    original = (root / "acquisition.json").is_file()
    if require_original and not original:
        raise ValueError("Diagnostic source cannot satisfy original Native delivery")
    acquisition = json.loads((root / "acquisition.json").read_text()) if original else {}
    if original:
        provenance = json.loads((root / "acquisition-provenance.json").read_text())
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False, "Original provenance missing")
    else:
        note = json.loads((root / "diagnostic-source-note.json").read_text())
        require(note.get("source_kind") == "synthetic_diagnostic_fixture" and
                note.get("case_id") == case_id, "Diagnostic provenance differs")
    names = ("protected-lane-history.jsonl", "protected-lane-scene.json", "trace.jsonl",
             "video_frames.jsonl", *[name + ".mkv" for name in CAMERAS])
    seals = {}
    for name in names:
        path = root / name
        require(path.is_file() and not path.is_symlink(), "Missing exact saved source: " + name)
        seals[name] = sha(path)
        if original:
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == seals[name], "Original source seal differs: " + name)
    history, trace, mapping = [rows(root / name) for name in names[:1] + names[2:4]]
    require(len(history) == len(trace) == len(mapping) == 900, "Incomplete frame history")
    frames = [row["original_frame"] for row in history]
    require(frames == list(range(frames[0], frames[0] + 900)), "Original frames not consecutive")
    for h, t, m in zip(history, trace, mapping):
        require(h["original_frame"] == t["frame"] == m["carla_frame"] and
                h["time_s"] == t["time_s"] == m["time_s"], "Actor/video time join differs")
        require(h["ego_id"] != h["protected_id"] and
                h["ego_kind"] == "motor_vehicle" and
                h["protected_kind"] in ("motorcycle", "moped") and
                h["ego_xy"] and h["protected_xy"], "Two original participants missing")
    scene = json.loads((root / "protected-lane-scene.json").read_text())
    require(scene["case_id"] == case_id and scene["protected_vehicle_class"] ==
            config["case"]["protected_kind"] and
            scene["ego_vehicle_class"] == "motor_vehicle", "Exact class/source scene differs")
    if original:
        site = scene["site"]
        require(all(site.get(k) for k in ("map_source_sha256", "lane_source_sha256",
                                          "highway_source_sha256", "motorcycle_class_source_sha256",
                                          "moped_class_source_sha256")), "Reviewed source context missing")
    cameras = {name: video(root / (name + ".mkv"), *size) for name, size in CAMERAS.items()}
    pixel_review = False
    if original:
        review = json.loads((root / "independent-pixel-review.json").read_text())
        require(review.get("case_id") == case_id and review.get("status") == "reviewed" and
                review.get("reviewer") and review.get("frame_map_sha256") ==
                seals["video_frames.jsonl"] and review.get("camera_sha256") == cameras,
                "Independent original pixel review incomplete")
        pixel_review = True
    result = json.loads((root / "result.json").read_text())
    require(result.get("case_id") == case_id and
            result.get("diagnostic_fixture") is (not original), "Attempt result identity differs")
    physical = bool(original and result.get("maneuver_completed") is True and
                    result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met")
    return {"format": "c147339-source-audit", "case_id": case_id, "native_source": original,
            "all_participants": True, "time_join": True, "full_video_decode": True,
            "actual_pixels": pixel_review, "physical_completion": physical,
            "original_frames": 900, "source_sha256": seals, "camera_sha256": cameras}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--require-original", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.require_original), sort_keys=True))
