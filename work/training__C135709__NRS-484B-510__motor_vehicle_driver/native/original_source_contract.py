"""Validate a retained restricted-zone attempt before saved measurement.

This checks source continuity and derives observable exchange/interference facts.
It does not infer a driver's purpose, sign authority, or legal compliance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 600
FPS = 20


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def sha(path: Path) -> str:
    require(path.is_file(), f"missing original source: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    sha(path)
    return json.loads(path.read_text(encoding="utf-8"))


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def rectangle(value, name: str) -> tuple[float, float, float, float]:
    require(isinstance(value, list) and len(value) == 4 and all(finite_number(x) for x in value),
            f"invalid original {name} rectangle")
    x0, y0, x1, y1 = value
    require(x0 < x1 and y0 < y1, f"invalid original {name} bounds")
    return x0, y0, x1, y1


def overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_video(path: Path) -> None:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries",
                            "stream=codec_name,r_frame_rate,nb_read_frames", "-of", "json",
                            str(path)], capture_output=True, text=True)
    require(probe.returncode == 0, f"original {path.name} failed video probe")
    streams = json.loads(probe.stdout).get("streams", [])
    require(len(streams) == 1 and streams[0].get("codec_name") == "ffv1" and
            streams[0].get("r_frame_rate") == "20/1" and
            streams[0].get("nb_read_frames") == str(FRAME_COUNT),
            f"original {path.name} must contain 600 lossless frames at 20 Hz")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    require(decoded.returncode == 0, f"original {path.name} failed full decode")


def validate(attempt: Path, review_path: Path) -> dict:
    attempt = attempt.resolve()
    capture = read_json(attempt / "capture-manifest.json")
    require(capture.get("source_kind") == "original_native", "original Native capture required")
    require(capture.get("frame_count") == FRAME_COUNT and capture.get("fps") == FPS,
            "original duration must be 600 frames at 20 Hz")
    require(capture.get("closed") is True and capture.get("world_restored") is True,
            "capture must close and restore the world")
    zone_path = attempt / "zone-survey.json"
    actor_path = attempt / "actor-frames.jsonl"
    join_path = attempt / "camera-frames.jsonl"
    zone = read_json(zone_path)
    zone_box = rectangle(zone.get("bounds_m"), "restricted zone")
    require(zone.get("map_sha256") == capture.get("map_sha256") and
            isinstance(zone.get("sign_actor_id"), int), "zone/map/sign source binding absent")
    require(isinstance(zone.get("sign_text_readback"), str) and zone["sign_text_readback"],
            "sign readback absent")
    video = capture.get("video_sources")
    require(isinstance(video, dict) and set(video) == set(CAMERAS), "four original videos required")
    source_hashes = {"capture-manifest.json": sha(attempt / "capture-manifest.json"),
                     "zone-survey.json": sha(zone_path),
                     "actor-frames.jsonl": sha(actor_path),
                     "camera-frames.jsonl": sha(join_path)}
    for name in CAMERAS:
        item = video[name]
        require(isinstance(item, dict) and item.get("path") == f"{name}.mkv",
                f"original {name} video declaration absent")
        actual = sha(attempt / item["path"])
        require(actual == item.get("sha256"), f"original {name} video hash mismatch")
        source_hashes[item["path"]] = actual
        check_video(attempt / item["path"])
    review = read_json(review_path)
    require(review.get("source_sha256") == source_hashes,
            "independent source review is missing or stale")
    require(review.get("sign_authority") in ("verified", "unverified", "rejected") and
            review.get("sign_pixel_status") in ("visible", "unverified", "not_visible"),
            "sign authority and pixel review required")
    require(review.get("restricted_purpose") and review.get("reviewer"),
            "named purpose review required")
    actors = [json.loads(line) for line in actor_path.read_text(encoding="utf-8").splitlines()]
    joins = [json.loads(line) for line in join_path.read_text(encoding="utf-8").splitlines()]
    require(len(actors) == len(joins) == FRAME_COUNT, "600 original actor and camera rows required")
    stopped = []
    passenger = []
    waiting = []
    previous_occupants = None
    for i, (row, join) in enumerate(zip(actors, joins)):
        require(row.get("frame") == join.get("frame") == i,
                f"original frame identity mismatch at {i}")
        require(row.get("native_frame") == join.get("native_frame") and
                isinstance(row.get("native_frame"), int), f"Native frame join mismatch at {i}")
        require(row.get("elapsed_s") == i / FPS, f"original clock mismatch at {i}")
        require(join.get("cameras") == {name: i for name in CAMERAS},
                f"four camera frame joins missing at {i}")
        ego_box = rectangle(row.get("ego_body_m"), "ego body")
        require(finite_number(row.get("ego_speed_mps")) and row["ego_speed_mps"] >= 0,
                f"invalid original ego speed at {i}")
        require(isinstance(row.get("occupant_actor_ids"), list) and
                all(isinstance(x, int) for x in row["occupant_actor_ids"]),
                f"original occupant identities absent at {i}")
        require(isinstance(row.get("door_open"), bool), f"door readback absent at {i}")
        others = row.get("other_vehicles")
        require(isinstance(others, list), f"other vehicle source absent at {i}")
        in_zone = overlaps(ego_box, zone_box)
        is_stopped = in_zone and row["ego_speed_mps"] <= 0.05
        stopped.append(is_stopped)
        current_occupants = tuple(row["occupant_actor_ids"])
        exchange = previous_occupants is not None and current_occupants != previous_occupants
        passenger.append(is_stopped and row["door_open"] and exchange)
        previous_occupants = current_occupants
        waiting_now = False
        for vehicle in others:
            require(isinstance(vehicle.get("actor_id"), int) and
                    finite_number(vehicle.get("speed_mps")) and vehicle["speed_mps"] >= 0,
                    f"other vehicle original identity or speed absent at {i}")
            other_box = rectangle(vehicle.get("body_m"), "other vehicle body")
            require(isinstance(vehicle.get("requesting_zone_entry"), bool),
                    f"other vehicle entry request source absent at {i}")
            waiting_now |= (vehicle["speed_mps"] <= 0.05 or vehicle["requesting_zone_entry"]) and overlaps(other_box, zone_box)
        waiting.append(is_stopped and waiting_now)
    return {"format": "restricted-zone-original-source-check-v1",
            "source_kind": "original_native",
            "source_sha256": source_hashes,
            "review_sha256": sha(review_path),
            "frame_count": FRAME_COUNT,
            "stopped_in_zone_frames": sum(stopped),
            "occupant_identity_change_frames_with_door_open": sum(passenger),
            "requested_waiting_or_entering_overlap_frames": sum(waiting),
            "restricted_purpose_review": review["restricted_purpose"],
            "sign_authority_review": review["sign_authority"],
            "sign_pixel_status": review["sign_pixel_status"],
            "subject_purpose": "unverified",
            "actual_passenger_loading": "unverified",
            "waiting_driver_purpose": "unverified",
            "temporary_judgment": "unreviewed",
            "legal_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.attempt, args.review), sort_keys=True))
