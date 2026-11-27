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
import xml.etree.ElementTree as ET

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 600
FPS = 20
AID = "training__C135709__NRS-484B-510__motor_vehicle_driver"
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2",
            "stop_only", "stand_only")
REVIEW_FINDINGS = ("subject_purpose", "actual_passenger_loading",
                   "waiting_driver_restricted_purpose", "interference",
                   "temporary_stop")


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
    kind = capture.get("source_kind")
    require(kind in ("original_native", "synthetic_fixture"),
            "original Native or explicitly synthetic source-shape fixture required")
    if kind == "synthetic_fixture":
        marker = read_json(attempt / "acquisition-provenance.json")
        require(marker.get("provenance_kind") == "synthetic_fixture" and
                marker.get("diagnostic_fixture") is True,
                "synthetic source-shape packet lacks diagnostic provenance")
    case_id = capture.get("case_id")
    require(case_id in {f"{AID}__{suffix}" for suffix in SUFFIXES},
            "exact original case identity required")
    require(capture.get("frame_count") == FRAME_COUNT and capture.get("fps") == FPS,
            "original duration must be 600 frames at 20 Hz")
    require(capture.get("closed") is True and capture.get("world_restored") is True,
            "capture must close and restore the world")
    zone_path = attempt / "zone-survey.json"
    map_path = attempt / "road.xodr"
    actor_path = attempt / "actor-frames.jsonl"
    join_path = attempt / "camera-frames.jsonl"
    zone = read_json(zone_path)
    map_sha256 = sha(map_path)
    try:
        map_root = ET.fromstring(map_path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        raise ValueError("original OpenDRIVE map is malformed") from exc
    zone_box = rectangle(zone.get("bounds_m"), "restricted zone")
    require(zone.get("map_sha256") == capture.get("map_sha256") == map_sha256 and
            zone.get("sign_id") == "510", "zone/map/sign source binding absent")
    require(isinstance(zone.get("sign_text_readback"), str) and zone["sign_text_readback"],
            "sign readback absent")
    signs = [item for item in map_root.findall(".//signal")
             if item.attrib.get("id") == zone["sign_id"]]
    require(len(signs) == 1 and signs[0].attrib.get("name") == zone["sign_text_readback"],
            "sign identity or text absent from original map")
    video = capture.get("video_sources")
    require(isinstance(video, dict) and set(video) == set(CAMERAS), "four original videos required")
    source_hashes = {"capture-manifest.json": sha(attempt / "capture-manifest.json"),
                     "road.xodr": map_sha256,
                     "zone-survey.json": sha(zone_path),
                     "actor-frames.jsonl": sha(actor_path),
                     "camera-frames.jsonl": sha(join_path),
                     "trace.jsonl": sha(attempt / "trace.jsonl"),
                     "video_frames.jsonl": sha(attempt / "video_frames.jsonl")}
    if kind == "original_native":
        seal = read_json(attempt / "capture-seal.json")
        require(seal.get("format") == "worker-sealed-capture" and
                seal.get("provenance_kind") == "native" and
                seal.get("frames") == FRAME_COUNT and
                seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
                seal.get("restoration", {}).get("restored") is True and
                set(seal.get("encoder_exit_codes", {})) == set(CAMERAS) and
                all(code == 0 for code in seal["encoder_exit_codes"].values()),
                "original Native closure is absent or incomplete")
        for name, digest in seal.get("sources", {}).items():
            require(sha(attempt / name) == digest, "sealed original source changed: " + name)
        require(all(seal.get("sources", {}).get(name) == digest for name, digest in source_hashes.items()),
                "original source omitted from Native seal")
        source_hashes["capture-seal.json"] = sha(attempt / "capture-seal.json")
    for name in CAMERAS:
        item = video[name]
        require(isinstance(item, dict) and item.get("path") == f"{name}.mkv",
                f"original {name} video declaration absent")
        actual = sha(attempt / item["path"])
        require(actual == item.get("sha256"), f"original {name} video hash mismatch")
        source_hashes[item["path"]] = actual
        check_video(attempt / item["path"])
    review = read_json(review_path)
    require(review.get("case_id") == case_id, "review binds another exact case")
    require(review.get("source_sha256") == source_hashes,
            "independent source review is missing or stale")
    require(review.get("sign_authority") in ("verified", "unverified", "rejected") and
            review.get("sign_pixel_status") in ("visible", "unverified", "not_visible"),
            "sign authority and pixel review required")
    require(review.get("restricted_purpose") and review.get("reviewer"),
            "named purpose review required")
    findings = review.get("original_findings")
    require(isinstance(findings, dict) and set(findings) == set(REVIEW_FINDINGS),
            "distinct original purpose, loading, interference and timing findings required")
    for name, finding in findings.items():
        require(isinstance(finding, dict) and
                finding.get("status") in ("verified", "unverified", "rejected") and
                isinstance(finding.get("source_refs"), list),
                "incomplete independent original finding: " + name)
        refs = finding["source_refs"]
        require(all(isinstance(ref, str) and ref in source_hashes for ref in refs) and
                (finding["status"] == "unverified" or bool(refs)),
                "original finding lacks source citation: " + name)
    actors = [json.loads(line) for line in actor_path.read_text(encoding="utf-8").splitlines()]
    joins = [json.loads(line) for line in join_path.read_text(encoding="utf-8").splitlines()]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    frame_map = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(actors) == len(joins) == len(trace) == len(frame_map) == FRAME_COUNT,
            "600 original actor, camera, trace and frame-map rows required")
    stopped = []
    departures = []
    moving_after_departure = []
    passenger = []
    waiting = []
    previous_nearby_passengers = None
    for i, (row, join) in enumerate(zip(actors, joins)):
        require(row.get("frame") == join.get("frame") == i,
                f"original frame identity mismatch at {i}")
        require(row.get("native_frame") == join.get("native_frame") and
                isinstance(row.get("native_frame"), int), f"Native frame join mismatch at {i}")
        require(row.get("elapsed_s") == i / FPS, f"original clock mismatch at {i}")
        require(join.get("cameras") == {name: i for name in CAMERAS},
                f"four camera frame joins missing at {i}")
        native_frame = row["native_frame"]
        require(trace[i].get("frame") == frame_map[i].get("carla_frame") ==
                frame_map[i].get("native_frame") == native_frame and
                frame_map[i].get("video_frame") == i and
                trace[i].get("time_s") == frame_map[i].get("time_s") == i / FPS and
                frame_map[i].get("camera_native_frames") ==
                {name: native_frame for name in CAMERAS},
                f"original trace/frame map join mismatch at {i}")
        ego_box = rectangle(row.get("ego_body_m"), "ego body")
        require(finite_number(row.get("ego_speed_mps")) and row["ego_speed_mps"] >= 0,
                f"invalid original ego speed at {i}")
        center = [(ego_box[0] + ego_box[2]) / 2, (ego_box[1] + ego_box[3]) / 2]
        require(trace[i].get("position_m") == center and
                trace[i].get("speed_mps") == row["ego_speed_mps"] and
                finite_number(trace[i].get("speed_mph")) and
                abs(trace[i]["speed_mph"] * 0.44704 - row["ego_speed_mps"]) < 1e-6,
                f"original trace/body motion differs at {i}")
        require(isinstance(row.get("passenger_actor_ids_near_vehicle"), list) and
                all(isinstance(x, int) for x in row["passenger_actor_ids_near_vehicle"]),
                f"original nearby passenger identities absent at {i}")
        require(isinstance(row.get("door_open_request"), bool), f"door control request absent at {i}")
        expected_departure = (300 if case_id.endswith("__stop_only") else
                              500 if case_id.endswith("__stand_only") else None)
        departure_requested = row.get("departure_requested", False)
        require(isinstance(departure_requested, bool) and
                departure_requested == (expected_departure is not None and i >= expected_departure),
                f"departure request differs from exact case at {i}")
        others = row.get("other_vehicles")
        require(isinstance(others, list), f"other vehicle source absent at {i}")
        in_zone = overlaps(ego_box, zone_box)
        is_stopped = in_zone and row["ego_speed_mps"] <= 0.05
        stopped.append(is_stopped)
        departures.append(departure_requested)
        moving_after_departure.append(departure_requested and row["ego_speed_mps"] > 0.05)
        current_nearby_passengers = tuple(row["passenger_actor_ids_near_vehicle"])
        exchange = previous_nearby_passengers is not None and current_nearby_passengers != previous_nearby_passengers
        passenger.append(is_stopped and row["door_open_request"] and exchange)
        previous_nearby_passengers = current_nearby_passengers
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
            "source_kind": kind,
            "case_id": case_id,
            "source_sha256": source_hashes,
            "review_sha256": sha(review_path),
            "frame_count": FRAME_COUNT,
            "stopped_in_zone_frames": sum(stopped),
            "departure_requested_frames": sum(departures),
            "moving_after_departure_frames": sum(moving_after_departure),
            "nearby_passenger_identity_change_frames_with_door_request": sum(passenger),
            "requested_waiting_or_entering_overlap_frames": sum(waiting),
            "restricted_purpose_review": review["restricted_purpose"],
            "sign_authority_review": review["sign_authority"],
            "sign_pixel_status": review["sign_pixel_status"],
            "subject_purpose": findings["subject_purpose"],
            "actual_passenger_loading": findings["actual_passenger_loading"],
            "waiting_driver_restricted_purpose": findings["waiting_driver_restricted_purpose"],
            "interference": findings["interference"],
            "temporary_stop": findings["temporary_stop"],
            "legal_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.attempt, args.review), sort_keys=True))
