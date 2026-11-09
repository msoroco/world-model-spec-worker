"""Measure a source-bound C111662 capture; never infer a legal verdict."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from build import FRAMES, RATE
from check import check

CAMERAS = ("ego_view", "turn_view", "overview")
LANES = {
    "west_eastbound_outer": (403, -3),
    "west_westbound_outer": (403, 3),
    "junction_eastbound_outer": (404, -3),
    "junction_westbound_outer": (404, 3),
    "east_eastbound_outer": (405, -3),
    "south_crossroad": (406, -3),
    "junction_crossroad": (407, -3),
    "north_crossroad": (408, -3),
}
FIXTURE_MEDIA = b"C111662 SYNTHETIC FIXTURE; NOT VIDEO\n"


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
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(path)],
                capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise ValueError("ffprobe unavailable") from exc
        if result.returncode:
            raise ValueError("Original camera media unreadable")
        streams = json.loads(result.stdout).get("streams", [])
        if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
                streams[0].get("nb_read_frames") != str(FRAMES):
            raise ValueError("Original FFV1 frame contract")
    return sha(path)


def process(bundle, directory, review_path, *, synthetic_fixture=False):
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = rows(bundle / "requested-tracks.jsonl")
    raw_path, video_path = directory / "native-raw-actors.jsonl", directory / "video_frames.jsonl"
    map_path, report_path = directory / "native-map-readback.json", directory / "native-capture-report.json"
    raw, video = rows(raw_path), rows(video_path)
    mapping, report, review = (json.loads(p.read_text()) for p in (map_path, report_path, review_path))
    if len(requests) != FRAMES or len(raw) != FRAMES or len(video) != FRAMES:
        raise ValueError("Exactly 800 joined frames required")
    kind = "synthetic_fixture" if synthetic_fixture else "original_native"
    review_kind = kind + "_review"
    if (mapping.get("source_kind") != kind or
            mapping.get("road_sha256") != sha(bundle / "district-crossroads.xodr") or
            mapping.get("junction_id") != 1 or
            not isinstance(mapping.get("native_map_sha256"), str) or
            len(mapping["native_map_sha256"]) != 64 or
            type(mapping.get("ego_actor_id")) is not int or
            mapping.get("authored_business_district") is not True or
            mapping.get("district_designation_verified") is not False or
            mapping.get("legal_verdict") is not None):
        raise ValueError("Generated map receipt mismatch")
    for name, (road_id, lane_id) in LANES.items():
        lane = mapping.get("lane_readback", {}).get(name, {})
        point = lane.get("native_xyz_m")
        if (lane.get("road_id") != road_id or lane.get("lane_id") != lane_id or
                "Driving" not in lane.get("lane_type", "") or
                not isinstance(point, list) or len(point) != 3 or not all(map(finite, point))):
            raise ValueError("Generated lane readback mismatch")
    if (report.get("case_id") != cfg["case_id"] or report.get("candidate_id") != cfg["candidate_id"] or
            report.get("config_sha256") != sha(bundle / "config.json") or
            report.get("requested_frames") != FRAMES or report.get("observed_frames") != FRAMES or
            report.get("error") is not None or report.get("restoration", {}).get("restored") is not True or
            report.get("accepted") is not False or report.get("delivery_ready") is not False or
            report.get("legal_verdict") is not None):
        raise ValueError("Capture or restoration receipt mismatch")
    media = {name + ".mkv": media_hash(directory / (name + ".mkv"), synthetic_fixture)
             for name in CAMERAS}
    review_flags = ("vehicle_and_centerline_visible", "turn_path_visible",
                    "intersection_extent_reviewed", "district_designation_reviewed",
                    "divided_highway_exception_reviewed")
    if (review.get("format") != "c111662-4033-original-review-v1" or
            review.get("source_kind") != review_kind or
            not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"].strip() or
            review.get("case_id") != cfg["case_id"] or review.get("candidate_id") != cfg["candidate_id"] or
            review.get("raw_sha256") != sha(raw_path) or
            review.get("video_frames_sha256") != sha(video_path) or
            review.get("map_sha256") != sha(map_path) or
            review.get("capture_report_sha256") != sha(report_path) or
            review.get("media_sha256") != media or
            any(type(review.get(flag)) is not bool for flag in review_flags)):
        raise ValueError("Source-hashed visual review mismatch")
    native_origin = raw[0].get("native_frame")
    if type(native_origin) is not int:
        raise ValueError("Native frame origin missing")
    actor_ids, points, headings, speeds = set(), [], [], []
    for i, (request, observed, image) in enumerate(zip(requests, raw, video)):
        t = (i + 1) / RATE
        if (request.get("frame") != i or observed.get("frame") != i or
                observed.get("request_frame") != i or image.get("video_frame") != i or
                observed.get("native_frame") != native_origin + i or
                image.get("native_frame") != native_origin + i or
                observed.get("source_kind") != kind or
                not finite(observed.get("time_s")) or not finite(image.get("time_s")) or
                abs(observed["time_s"] - t) > .005 or
                abs(image["time_s"] - observed["time_s"]) > 1e-6 or
                observed.get("requested_phase") != request.get("requested_phase") or
                observed.get("authored_business_district") is not True or
                observed.get("district_designation_verified") is not False or
                observed.get("legal_verdict") is not None):
            raise ValueError("Request, actor and video join mismatch")
        ego = observed.get("ego", {})
        center, velocity, body = (ego.get(key) for key in
            ("center_native_xyz_m", "velocity_native_xyz_mps", "body_native_xyz_m"))
        if (type(ego.get("actor_id")) is not int or ego.get("blueprint") != cfg["ego_blueprint"] or
                not isinstance(center, list) or len(center) != 3 or not all(map(finite, center)) or
                not isinstance(velocity, list) or len(velocity) != 3 or not all(map(finite, velocity)) or
                not isinstance(body, list) or len(body) != 8 or
                any(not isinstance(p, list) or len(p) != 3 or not all(map(finite, p)) for p in body) or
                not finite(ego.get("yaw_deg")) or not finite(ego.get("speed_mps")) or
                abs(ego["speed_mps"] - math.sqrt(sum(v*v for v in velocity))) > .02 or
                math.dist(center, [sum(p[k] for p in body)/8 for k in range(3)]) > 1 or
                observed.get("ego_road_id") not in (403, 404, 405, None)):
            raise ValueError("Actor body, velocity or road mismatch")
        actor_ids.add(ego["actor_id"])
        if points and math.dist(center, points[-1]) > max(ego["speed_mps"], speeds[-1]) / RATE + .5:
            raise ValueError("Actor displacement discontinuity")
        points.append(center)
        speeds.append(ego["speed_mps"])
        headings.append(ego["yaw_deg"])
    if actor_ids != {mapping["ego_actor_id"]}:
        raise ValueError("Actor identity discontinuity")
    first_yaw, last_yaw = headings[0], headings[-1]
    heading_change = abs((last_yaw - first_yaw + 180) % 360 - 180)
    cross = next((p for a, p in zip(points, points[1:]) if a[1] <= 0 < p[1]), None)
    if (points[0][1] > -4 or points[-1][1] < 4 or cross is None or
            abs(cross[0] - cfg["requested_turn_center_x_m"]) > 8 or heading_change < 150):
        raise ValueError("Observed U-turn geometry missing")
    zone = requests[0]["authored_intersection_zone_x_m"]
    in_zone = zone[0] <= cross[0] <= zone[1]
    expected = cfg["case_id"].endswith("__contrast")
    if in_zone != expected:
        raise ValueError("Observed crossing location differs from paired case")
    return {"format": "c111662-4033-original-saved-v1",
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "source_kind": kind, "frames_joined": FRAMES,
            "observed_crossing_x_m": round(cross[0], 4),
            "observed_heading_change_deg": round(heading_change, 4),
            "crossing_in_authored_intersection_zone": in_zone,
            "raw_sha256": sha(raw_path), "review_sha256": sha(review_path),
            "district_designation_verified": False,
            "divided_highway_exception_legally_verified": False,
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
