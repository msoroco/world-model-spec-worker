"""Source-bound saved processing for a divided-highway Native capture."""
import json
import math
from pathlib import Path

from build import RATE
from divided_opening import FRAMES, OPENING_X, check
from process_original import CAMERAS, finite, media_hash, rows, sha

LANES = {
    "reference_eastbound": (503, -2, "Driving"),
    "reference_westbound": (503, 2, "Driving"),
    "reference_median": (503, 1, "Median"),
    "opening_eastbound": (504, -2, "Driving"),
    "opening_crossing": (504, 1, "Driving"),
    "opening_westbound": (504, 2, "Driving"),
    "departure_median": (505, 1, "Median"),
}
REVIEW_FLAGS = (
    "vehicle_and_median_visible", "turn_path_visible",
    "opening_extent_reviewed", "district_designation_reviewed",
    "appropriate_crossing_place_reviewed",
)


def process(bundle, directory, review_path, *, synthetic_fixture=False):
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = rows(bundle / "requested-tracks.jsonl")
    raw_path = directory / "native-raw-actors.jsonl"
    video_path = directory / "video_frames.jsonl"
    map_path = directory / "native-map-readback.json"
    report_path = directory / "native-capture-report.json"
    raw, video = rows(raw_path), rows(video_path)
    mapping, report, review = (
        json.loads(path.read_text()) for path in
        (map_path, report_path, review_path))
    if len(requests) != FRAMES or len(raw) != FRAMES or len(video) != FRAMES:
        raise ValueError("Exactly 800 divided capture joins required")
    kind = "synthetic_fixture" if synthetic_fixture else "original_native"
    if (mapping.get("source_kind") != kind or
            mapping.get("road_sha256") != sha(bundle / "divided-highway.xodr") or
            not isinstance(mapping.get("native_map_sha256"), str) or
            len(mapping["native_map_sha256"]) != 64 or
            type(mapping.get("ego_actor_id")) is not int or
            mapping.get("authored_divided_highway") is not True or
            mapping.get("district_designation_verified") is not False or
            mapping.get("opening_exception_legally_verified") is not False or
            mapping.get("legal_verdict") is not None):
        raise ValueError("Generated divided map receipt mismatch")
    for name, (road_id, lane_id, lane_type) in LANES.items():
        lane = mapping.get("lane_readback", {}).get(name, {})
        point = lane.get("native_xyz_m")
        if (lane.get("road_id") != road_id or lane.get("lane_id") != lane_id or
                lane_type not in lane.get("lane_type", "") or
                not isinstance(point, list) or len(point) != 3 or
                not all(map(finite, point))):
            raise ValueError("Generated median or opening readback mismatch")
    if (report.get("case_id") != cfg["case_id"] or
            report.get("candidate_id") != cfg["candidate_id"] or
            report.get("config_sha256") != sha(bundle / "config.json") or
            report.get("requested_frames") != FRAMES or
            report.get("observed_frames") != FRAMES or
            report.get("error") is not None or
            report.get("restoration", {}).get("restored") is not True or
            report.get("accepted") is not False or
            report.get("delivery_ready") is not False or
            report.get("legal_verdict") is not None):
        raise ValueError("Divided capture or restoration receipt mismatch")
    media = {name + ".mkv": media_hash(directory / (name + ".mkv"), synthetic_fixture)
             for name in CAMERAS}
    if (review.get("format") != "c111662-4033-divided-original-review-v1" or
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
        raise ValueError("Source-hashed divided visual review mismatch")
    origin = raw[0].get("native_frame")
    if type(origin) is not int:
        raise ValueError("Native frame origin missing")
    actor_ids, centers, headings, speeds, bodies = set(), [], [], [], []
    for i, (request, observed, image) in enumerate(zip(requests, raw, video)):
        t = (i + 1) / RATE
        if (request.get("frame") != i or observed.get("frame") != i or
                observed.get("request_frame") != i or
                image.get("video_frame") != i or
                observed.get("native_frame") != origin + i or
                image.get("native_frame") != origin + i or
                observed.get("source_kind") != kind or
                not finite(observed.get("time_s")) or
                not finite(image.get("time_s")) or
                abs(observed["time_s"] - t) > .005 or
                abs(image["time_s"] - observed["time_s"]) > 1e-6 or
                observed.get("requested_phase") != request.get("requested_phase") or
                observed.get("authored_divided_highway") is not True or
                observed.get("district_designation_verified") is not False or
                observed.get("opening_exception_legally_verified") is not False or
                observed.get("legal_verdict") is not None):
            raise ValueError("Divided request/actor/video join mismatch")
        ego = observed.get("ego", {})
        center = ego.get("center_native_xyz_m")
        velocity = ego.get("velocity_native_xyz_mps")
        body = ego.get("body_native_xyz_m")
        if (type(ego.get("actor_id")) is not int or
                ego.get("blueprint") != cfg["ego_blueprint"] or
                not isinstance(center, list) or len(center) != 3 or
                not all(map(finite, center)) or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(map(finite, velocity)) or
                not isinstance(body, list) or len(body) != 8 or
                any(not isinstance(p, list) or len(p) != 3 or
                    not all(map(finite, p)) for p in body) or
                not finite(ego.get("yaw_deg")) or
                not finite(ego.get("speed_mps")) or
                abs(ego["speed_mps"] -
                    math.sqrt(sum(v*v for v in velocity))) > .02 or
                math.dist(center, [sum(p[k] for p in body)/8
                                   for k in range(3)]) > 1 or
                observed.get("ego_road_id") not in (503, 504, 505, None)):
            raise ValueError("Divided actor body, velocity or road mismatch")
        if centers and math.dist(center, centers[-1]) > \
                max(ego["speed_mps"], speeds[-1]) / RATE + .5:
            raise ValueError("Divided actor displacement discontinuity")
        actor_ids.add(ego["actor_id"])
        centers.append(center)
        headings.append(ego["yaw_deg"])
        speeds.append(ego["speed_mps"])
        bodies.append(body)
    if actor_ids != {mapping["ego_actor_id"]}:
        raise ValueError("Divided actor identity discontinuity")
    heading_change = abs((headings[-1] - headings[0] + 180) % 360 - 180)
    crossing_index = next(
        (i for i, (before, after) in enumerate(zip(centers, centers[1:]), 1)
         if before[1] <= 0 < after[1]), None)
    if (centers[0][1] > -4 or centers[-1][1] < 4 or
            crossing_index is None or heading_change < 150):
        raise ValueError("Observed divided U-turn missing")
    cross = centers[crossing_index]
    if abs(cross[0] - cfg["requested_turn_center_x_m"]) > 8:
        raise ValueError("Observed divided crossing far from requested center")
    in_opening = OPENING_X[0] <= cross[0] <= OPENING_X[1]
    if in_opening != cfg["case_id"].endswith("__divided_opening"):
        raise ValueError("Observed crossing differs from opening case")
    return {
        "format": "c111662-4033-divided-original-saved-v1",
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "source_kind": kind, "frames_joined": FRAMES,
        "observed_crossing_x_m": round(cross[0], 4),
        "observed_crossing_frame": crossing_index,
        "observed_heading_change_deg": round(heading_change, 4),
        "crossing_in_authored_opening": in_opening,
        "raw_sha256": sha(raw_path), "review_sha256": sha(review_path),
        "district_designation_verified": False,
        "opening_exception_legally_verified": False,
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
