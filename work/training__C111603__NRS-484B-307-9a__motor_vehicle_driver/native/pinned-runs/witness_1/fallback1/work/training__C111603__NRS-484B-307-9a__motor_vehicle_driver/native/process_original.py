"""Source-bound C111603 original capture measurement, without a legal verdict."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from build import FRAMES, RATE, check, digest

CAMERAS = ("ego_view", "signal_view", "overview")
LANES = {"south_approach": (1, -1), "east_departure": (2, -1)}
FIXTURE_MEDIA = b"C111603 SYNTHETIC FIXTURE; NOT VIDEO\n"
REVIEW_FLAGS = (
    "directional_arrow_pixels_reviewed", "signal_governs_ego_reviewed",
    "other_traffic_lawfulness_reviewed", "yield_relation_reviewed",
    "crosswalk_pedestrian_context_reviewed")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def media_hash(path, synthetic_fixture):
    path = Path(path)
    if synthetic_fixture:
        if path.read_bytes() != FIXTURE_MEDIA:
            raise ValueError("Synthetic fixture media changed")
    else:
        try:
            completed = subprocess.run([
                "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(path)],
                capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise ValueError("ffprobe unavailable") from exc
        if completed.returncode:
            raise ValueError("Original camera media unreadable")
        streams = json.loads(completed.stdout).get("streams", [])
        if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
                streams[0].get("nb_read_frames") != str(FRAMES)):
            raise ValueError("Original FFV1 frame contract")
    return sha(path)


def actor_shape(actor, blueprint):
    center = actor.get("center_native_xyz_m")
    velocity = actor.get("velocity_native_xyz_mps")
    body = actor.get("body_native_xyz_m")
    if (type(actor.get("actor_id")) is not int or actor.get("blueprint") != blueprint or
            not isinstance(center, list) or len(center) != 3 or not all(map(finite, center)) or
            not isinstance(velocity, list) or len(velocity) != 3 or not all(map(finite, velocity)) or
            not isinstance(body, list) or len(body) != 8 or
            any(not isinstance(point, list) or len(point) != 3 or
                not all(map(finite, point)) for point in body) or
            not finite(actor.get("yaw_deg")) or not finite(actor.get("speed_mps")) or
            abs(actor["speed_mps"] - math.sqrt(sum(v*v for v in velocity))) > .02 or
            math.dist(center, [sum(point[k] for point in body)/8 for k in range(3)]) > 1):
        raise ValueError("Physical actor body, velocity or blueprint mismatch")
    return center, actor["speed_mps"]


def process(bundle, directory, review_path, *, synthetic_fixture=False):
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = rows(bundle / "requested-tracks.jsonl")
    raw_path, video_path = directory / "native-raw-actors.jsonl", directory / "video_frames.jsonl"
    map_path, report_path = directory / "native-map-readback.json", directory / "native-capture-report.json"
    raw, video = rows(raw_path), rows(video_path)
    mapping, report, review = (json.loads(path.read_text()) for path in
                               (map_path, report_path, review_path))
    if len(requests) != FRAMES or len(raw) != FRAMES or len(video) != FRAMES:
        raise ValueError("Exactly 480 joined frames required")
    kind = "synthetic_fixture" if synthetic_fixture else "original_native"
    if (mapping.get("source_kind") != kind or
            mapping.get("road_sha256") != digest(bundle / "arrow-intersection.xodr") or
            not isinstance(mapping.get("native_map_sha256"), str) or
            len(mapping["native_map_sha256"]) != 64 or
            type(mapping.get("red_actor_id")) is not int or
            type(mapping.get("arrow_actor_id")) is not int or
            mapping["red_actor_id"] == mapping["arrow_actor_id"] or
            type(mapping.get("ego_actor_id")) is not int or
            type(mapping.get("other_actor_id")) is not int or
            mapping["ego_actor_id"] == mapping["other_actor_id"] or
            mapping.get("directional_arrow_pixels_verified") is not False or
            mapping.get("signal_governs_ego_verified") is not False or
            mapping.get("other_traffic_lawfulness_verified") is not False or
            mapping.get("legal_verdict") is not None):
        raise ValueError("Generated map or signal receipt mismatch")
    for name, (road_id, lane_id) in LANES.items():
        lane = mapping.get("lane_readback", {}).get(name, {})
        point = lane.get("native_xyz_m")
        if (lane.get("road_id") != road_id or lane.get("lane_id") != lane_id or
                not isinstance(point, list) or len(point) != 3 or
                not all(map(finite, point))):
            raise ValueError("Generated lane readback mismatch")
    if (report.get("case_id") != cfg["case_id"] or
            report.get("candidate_id") != cfg["candidate_id"] or
            report.get("config_sha256") != digest(bundle / "config.json") or
            report.get("requested_frames") != FRAMES or
            report.get("observed_frames") != FRAMES or
            report.get("error") is not None or
            report.get("restoration", {}).get("restored") is not True or
            report.get("accepted") is not False or
            report.get("delivery_ready") is not False or
            report.get("legal_verdict") is not None):
        raise ValueError("Capture or restoration receipt mismatch")
    media = {name + ".mkv": media_hash(directory / (name + ".mkv"), synthetic_fixture)
             for name in CAMERAS}
    if (review.get("format") != "c111603-3079a-original-review-v1" or
            review.get("source_kind") != kind + "_review" or
            not isinstance(review.get("reviewer_id"), str) or
            not review["reviewer_id"].strip() or
            review.get("case_id") != cfg["case_id"] or
            review.get("candidate_id") != cfg["candidate_id"] or
            review.get("raw_sha256") != sha(raw_path) or
            review.get("video_frames_sha256") != sha(video_path) or
            review.get("map_sha256") != sha(map_path) or
            review.get("capture_report_sha256") != sha(report_path) or
            review.get("media_sha256") != media or
            any(type(review.get(flag)) is not bool for flag in REVIEW_FLAGS)):
        raise ValueError("Source-hashed visual review mismatch")
    native_origin = raw[0].get("native_frame")
    if type(native_origin) is not int:
        raise ValueError("Native frame origin missing")
    ego_ids, other_ids, ego_points, other_points = set(), set(), [], []
    ego_speeds, other_speeds, headings = [], [], []
    red_frames = green_frames = 0
    for index, (request, observed, image) in enumerate(zip(requests, raw, video)):
        expected_t = (index + 1) / RATE
        if (request.get("frame") != index or observed.get("frame") != index or
                observed.get("request_frame") != index or image.get("video_frame") != index or
                observed.get("native_frame") != native_origin + index or
                image.get("native_frame") != native_origin + index or
                observed.get("source_kind") != kind or
                not finite(observed.get("time_s")) or not finite(image.get("time_s")) or
                abs(observed["time_s"] - expected_t) > .005 or
                abs(image["time_s"] - observed["time_s"]) > 1e-6 or
                observed.get("requested_phase") != request.get("requested_phase") or
                observed.get("red_actor_id") != mapping["red_actor_id"] or
                observed.get("arrow_actor_id") != mapping["arrow_actor_id"] or
                observed.get("directional_arrow_pixels_verified") is not False or
                observed.get("signal_governs_ego_verified") is not False or
                observed.get("other_traffic_lawfulness_verified") is not False or
                observed.get("legal_verdict") is not None):
            raise ValueError("Request, actor, signal and video join mismatch")
        if not str(observed.get("red_state", "")).endswith("Red"):
            raise ValueError("Native red head was not steady red")
        if not str(observed.get("arrow_state", "")).endswith("Green"):
            raise ValueError("Native arrow head was not green")
        red_frames += 1
        green_frames += 1
        ego = observed.get("ego", {})
        other = observed.get("other_vehicle", {})
        ego_center, ego_speed = actor_shape(ego, cfg["ego_blueprint"])
        other_center, other_speed = actor_shape(other, cfg["other_blueprint"])
        ego_ids.add(ego["actor_id"])
        other_ids.add(other["actor_id"])
        if ego_points and math.dist(ego_center, ego_points[-1]) > max(ego_speed, ego_speeds[-1])/RATE + .5:
            raise ValueError("Ego displacement discontinuity")
        if other_points and math.dist(other_center, other_points[-1]) > max(other_speed, other_speeds[-1])/RATE + .5:
            raise ValueError("Other-vehicle displacement discontinuity")
        ego_points.append(ego_center)
        other_points.append(other_center)
        ego_speeds.append(ego_speed)
        other_speeds.append(other_speed)
        headings.append(ego["yaw_deg"])
    if ego_ids != {mapping["ego_actor_id"]} or other_ids != {mapping["other_actor_id"]}:
        raise ValueError("Physical actor identity discontinuity")
    heading_change = abs((headings[-1] - headings[0] + 180) % 360 - 180)
    right_turn = heading_change >= 60 and ego_points[-1][0] > 5
    expected_right = cfg["requested_movement"] == "right_arrow_turn"
    hold_indices = [i for i, row in enumerate(requests) if row["requested_phase"] == "yield_hold"]
    observed_hold_max_speed = max(ego_speeds[i] for i in hold_indices)
    return {"format": "c111603-3079a-original-saved-v1",
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "source_kind": kind, "frames_joined": FRAMES,
            "observed_red_frames": red_frames, "observed_green_head_frames": green_frames,
            "observed_heading_change_deg": round(heading_change, 4),
            "observed_final_ego_xy_m": [round(v, 4) for v in ego_points[-1][:2]],
            "observed_movement_matches_request": right_turn == expected_right,
            "requested_yield_hold_max_observed_speed_mps": round(observed_hold_max_speed, 4),
            "raw_sha256": sha(raw_path), "review_sha256": sha(review_path),
            "directional_arrow_pixels_reviewed": review["directional_arrow_pixels_reviewed"],
            "signal_governs_ego_reviewed": review["signal_governs_ego_reviewed"],
            "other_traffic_lawfulness_reviewed": review["other_traffic_lawfulness_reviewed"],
            "yield_relation_reviewed": review["yield_relation_reviewed"],
            "crosswalk_pedestrian_context_reviewed": review["crosswalk_pedestrian_context_reviewed"],
            "original_native_observed": not synthetic_fixture,
            "legal_verdict": None, "accepted": False, "delivery_ready": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = process(args.bundle, args.capture_dir, args.review)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
