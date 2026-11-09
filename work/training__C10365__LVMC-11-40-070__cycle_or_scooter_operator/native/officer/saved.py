"""Saved-frame joins and measurements; never promote a requested cue to an observation."""
import json
import hashlib
import math
from pathlib import Path
import subprocess

from check import check

FRAMES = 480
RATE = 20


def read_rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_media(path):
    if not path.is_file():
        raise ValueError("Original FFV1 camera missing: " + path.name)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True, timeout=120)
    if probe.returncode:
        raise ValueError("Original FFV1 camera unreadable: " + path.name)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
            streams[0].get("nb_read_frames") != str(FRAMES):
        raise ValueError("Original FFV1 camera frame contract: " + path.name)
    return sha(path)


def process(bundle, raw, video, review, *, synthetic=False):
    bundle = Path(bundle)
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw_rows, video_rows = read_rows(raw), read_rows(video)
    requests = read_rows(bundle / "requested-tracks.jsonl")
    visual = json.loads(Path(review).read_text())
    if len(raw_rows) != FRAMES or len(video_rows) != FRAMES or len(requests) != FRAMES:
        raise ValueError("480 source frames required")
    if visual.get("source_kind") != ("synthetic_fixture" if synthetic else "original_native_review"):
        raise ValueError("Review source kind mismatch")
    if visual.get("case_id") != cfg["case_id"] or visual.get("candidate_id") != cfg["candidate_id"]:
        raise ValueError("Review identity mismatch")
    mapping = None
    if not synthetic:
        source_dir = Path(raw).parent
        if Path(video).parent != source_dir:
            raise ValueError("Original video join source directory differs")
        media_hashes = {}
        for name in ("overview.mkv", "rider_forward.mkv", "officer_side.mkv"):
            media_hashes[name] = verify_media(source_dir / name)
        map_path = source_dir / "native-map-readback.json"
        report_path = source_dir / "native-capture-report.json"
        if not map_path.is_file():
            raise ValueError("Original Native map readback missing")
        if not report_path.is_file():
            raise ValueError("Original Native capture report missing")
        mapping = json.loads(map_path.read_text())
        report = json.loads(report_path.read_text())
        landmark = mapping.get("stop_landmark_readback", {})
        if (mapping.get("source_kind") != "original_native" or
                mapping.get("road_sha256") != sha(bundle / "alley-stop.xodr") or
                landmark.get("id") != "3651" or landmark.get("road_id") != 365 or
                landmark.get("type") != "206" or
                not finite_number(landmark.get("s_m")) or
                abs(landmark["s_m"] - 50) > .5 or
                mapping.get("lane_readback") != {
                    str(x): {"road_id": 365, "lane_id": -1, "lane_type": "driving"}
                    for x in (20, 45, 55)}):
            raise ValueError("Original device readback mismatch")
        if (report.get("case_id") != cfg["case_id"] or
                report.get("candidate_id") != cfg["candidate_id"] or
                report.get("config_sha256") != sha(bundle / "config.json") or
                report.get("requested_frames") != FRAMES or
                report.get("observed_frames") != FRAMES or
                report.get("error") is not None or
                report.get("accepted") is not False or
                report.get("delivery_ready") is not False):
            raise ValueError("Original capture receipt mismatch")
        if (visual.get("media_sha256") != media_hashes or
                visual.get("raw_sha256") != sha(raw) or
                visual.get("video_frames_sha256") != sha(video) or
                visual.get("map_sha256") != sha(map_path) or
                visual.get("capture_report_sha256") != sha(report_path)):
            raise ValueError("Original visual review source hashes mismatch")
    speeds, front_x, rider_ids, officer_ids = [], [], set(), set()
    first_native = raw_rows[0].get("native_frame")
    previous_center = None
    for i, (row, v, request) in enumerate(zip(raw_rows, video_rows, requests)):
        if row.get("frame") != i or v.get("video_frame") != i:
            raise ValueError("Frame sequence changed")
        if (type(first_native) is not int or row.get("native_frame") != first_native + i or
                row.get("native_frame") != v.get("native_frame") or
                not finite_number(row.get("time_s")) or
                abs(row["time_s"] - (i + 1) / RATE) > .005 or
                not finite_number(v.get("time_s")) or
                abs(row["time_s"] - v["time_s"]) > 1e-6):
            raise ValueError("Native/video time join changed")
        if row.get("source_kind") != ("synthetic_fixture" if synthetic else "original_native"):
            raise ValueError("Raw source kind mismatch")
        rider, officer = row.get("rider", {}), row.get("officer_actor", {})
        if rider.get("blueprint") != cfg["rider_blueprint"] or \
                not str(officer.get("blueprint", "")).startswith("walker.pedestrian."):
            raise ValueError("Rider/officer actor class mismatch")
        if row.get("observed_road_id") != 365 or row.get("observed_lane_id") != -1:
            raise ValueError("Rider approach lane mismatch")
        if row.get("officer_cue_requested") != cfg["officer_cue_requested"]:
            raise ValueError("Officer request identity changed")
        if (row.get("requested_rider_x_m") != request["requested_rider_x_m"] or
                row.get("requested_speed_mps") != request["requested_speed_mps"]):
            raise ValueError("Original row/request identity changed")
        rider_ids.add(rider.get("actor_id"))
        officer_ids.add(officer.get("actor_id"))
        speed = rider.get("speed_mps")
        center = rider.get("center_native_xyz_m")
        velocity = rider.get("velocity_native_xyz_mps")
        vertices = rider.get("body_native_xyz_m")
        if (not finite_number(speed) or speed < 0 or
                not isinstance(center, list) or len(center) != 3 or
                not all(map(finite_number, center)) or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(map(finite_number, velocity)) or
                abs(math.sqrt(sum(vv * vv for vv in velocity)) - speed) > .01 or
                not isinstance(vertices, list) or len(vertices) != 8 or
                not all(isinstance(p, list) and len(p) == 3 and all(map(finite_number, p))
                        for p in vertices)):
            raise ValueError("Original body or speed invalid")
        if previous_center is not None and math.dist(center, previous_center) > speed / RATE + .5:
            raise ValueError("Rider speed/displacement continuity")
        previous_center = center
        officer_center = officer.get("center_native_xyz_m")
        officer_velocity = officer.get("velocity_native_xyz_mps")
        officer_body = officer.get("body_native_xyz_m")
        if (not isinstance(officer_center, list) or len(officer_center) != 3 or
                not all(map(finite_number, officer_center)) or
                not isinstance(officer_velocity, list) or len(officer_velocity) != 3 or
                not all(map(finite_number, officer_velocity)) or
                not finite_number(officer.get("speed_mps")) or
                abs(math.sqrt(sum(vv * vv for vv in officer_velocity)) -
                    officer["speed_mps"]) > .01 or
                not isinstance(officer_body, list) or len(officer_body) != 8 or
                not all(isinstance(p, list) and len(p) == 3 and all(map(finite_number, p))
                        for p in officer_body)):
            raise ValueError("Officer body or speed invalid")
        speeds.append(speed)
        front_x.append(max(p[0] for p in vertices))
    if len(rider_ids) != 1 or len(officer_ids) != 1 or None in rider_ids | officer_ids:
        raise ValueError("Actor identity discontinuity")
    if rider_ids == officer_ids:
        raise ValueError("Rider/officer actor identity collapsed")
    if mapping is not None and (mapping.get("rider_actor_id") not in rider_ids or
                                mapping.get("officer_actor_id") not in officer_ids):
        raise ValueError("Original actor/map identity mismatch")
    stop_runs, current = [], 0
    for speed, front in zip(speeds, front_x):
        current = current + 1 if speed <= .25 and front < 50 else 0
        stop_runs.append(current)
    stopped = max(stop_runs) >= RATE
    crossing_frame = next((i for i, front in enumerate(front_x) if front > 50), None)
    if crossing_frame is not None and crossing_frame == 0:
        raise ValueError("No pre-crossing approach")
    reviewed = visual.get("reviewed_frames")
    if not isinstance(reviewed, list) or not reviewed or \
            any(type(i) is not int or i < 0 or i >= FRAMES for i in reviewed):
        raise ValueError("Visual review frame references invalid")
    if visual.get("device_id") != "3651" or visual.get("device_applicable") is not True:
        raise ValueError("Device applicability unreviewed")
    if visual.get("rider_class") != "bicycle":
        raise ValueError("Rider class unreviewed")
    if visual.get("officer_actor_id") != next(iter(officer_ids)):
        raise ValueError("Officer review actor join")
    direction = visual.get("officer_direction")
    if cfg["case_id"].endswith("probe_a"):
        if direction != "none_contrary" or not stopped or crossing_frame is not None:
            raise ValueError("Ordinary device response not demonstrated")
    else:
        direction_start = visual.get("direction_start_frame")
        direction_end = visual.get("direction_end_frame")
        if (direction != "proceed" or visual.get("officer_authority_reviewed") is not True or
                visual.get("direction_visible") is not True or crossing_frame is None or
                type(direction_start) is not int or type(direction_end) is not int or
                direction_start not in reviewed or direction_end not in reviewed or
                not 0 <= direction_start < direction_end < crossing_frame):
            raise ValueError("Contrary officer direction and response not demonstrated")
    if not synthetic and visual.get("reviewer") in (None, "", "synthetic"):
        raise ValueError("Independent original visual reviewer missing")
    margin = min(50 - f for f, s in zip(front_x, speeds) if s <= .25) \
        if stopped else None
    first_approach = next((i for i, f in enumerate(front_x) if f >= 40), None)
    latency = ((crossing_frame - first_approach) / RATE
               if crossing_frame is not None and first_approach is not None else None)
    separation = min(math.hypot(row["rider"]["center_native_xyz_m"][0] -
                                row["officer_actor"]["center_native_xyz_m"][0],
                                row["rider"]["center_native_xyz_m"][1] -
                                row["officer_actor"]["center_native_xyz_m"][1])
                     for row in raw_rows)
    visibility = visual.get("officer_cue_visibility")
    if not finite_number(visibility) or not 0 <= visibility <= 1:
        raise ValueError("Visibility measurement invalid")
    triggers = {
        "fallback1": margin is not None and margin < 3 or
                     latency is not None and latency < 2,
        "fallback2": visibility < .90,
        "fallback3": separation < 5,
    }
    return {
        "case_id": checked["case_id"], "candidate_id": checked["candidate_id"],
        "source_kind": "synthetic_fixture" if synthetic else "original_native",
        "frames": FRAMES, "stopped": stopped, "crossing_frame": crossing_frame,
        "stop_margin_m": margin, "crossing_latency_s": latency,
        "min_officer_rider_separation_m": separation,
        "officer_cue_visibility": visibility, "fallback_triggers": triggers,
        "officer_direction_reviewed": direction,
        "physical_legal_verdict": None, "delivery_ready": False,
    }
