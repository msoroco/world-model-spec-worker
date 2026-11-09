"""Source-bound saved measurements from an original, unaccepted C104496 capture."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from build import FRAMES, RATE
from check import check

CAMERAS = ("west_view", "east_view", "overview")
TURN_PHASES = ("forward_left", "reverse_right", "forward_left_finish")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def ffv1_frames(path):
    if not path.is_file():
        raise ValueError("Original camera media missing")
    try:
        run = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                              "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise ValueError("ffprobe unavailable for original media check") from exc
    if run.returncode:
        raise ValueError("Original camera media unreadable")
    streams = json.loads(run.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
            streams[0].get("nb_read_frames") != str(FRAMES):
        raise ValueError("Original FFV1 camera contract")
    return sha(path)


def actor(row, blueprint):
    if row.get("blueprint") != blueprint or type(row.get("actor_id")) is not int:
        raise ValueError("Original actor identity")
    center = row.get("center_native_xyz_m")
    velocity = row.get("velocity_native_xyz_mps")
    body = row.get("body_native_xyz_m")
    if (not isinstance(center, list) or len(center) != 3 or not all(map(finite, center)) or
            not isinstance(velocity, list) or len(velocity) != 3 or not all(map(finite, velocity)) or
            not isinstance(body, list) or len(body) != 8 or
            any(not isinstance(p, list) or len(p) != 3 or not all(map(finite, p)) for p in body) or
            not finite(row.get("yaw_deg")) or not finite(row.get("speed_mps")) or
            abs(row["speed_mps"] - math.sqrt(sum(v*v for v in velocity))) > .02):
        raise ValueError("Original actor body or velocity")
    return center, velocity, body


def roadway_distance(a, b, height):
    step = (b-a) / 200
    return abs(step) / 3 * sum((1 if i in (0, 200) else 4 if i % 2 else 2) *
        math.sqrt(1 + (height*(200-(a+i*step))/20000)**2) for i in range(201))


def process(bundle, directory, review_path, *, synthetic_fixture=False):
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw_path = directory / "native-raw-actors.jsonl"
    video_path = directory / "video_frames.jsonl"
    map_path = directory / "native-map-readback.json"
    capture_path = directory / "native-capture-report.json"
    requests, raw, video = lines(bundle / "requested-tracks.jsonl"), lines(raw_path), lines(video_path)
    mapping, report, review = (json.loads(path.read_text()) for path in
                               (map_path, capture_path, review_path))
    if len(requests) != FRAMES or len(raw) != FRAMES or len(video) != FRAMES:
        raise ValueError("700 request, actor and video frames required")
    expected_kind = "synthetic_fixture" if synthetic_fixture else "original_native"
    expected_review_kind = "synthetic_fixture_review" if synthetic_fixture else "original_native_review"
    if (mapping.get("source_kind") != expected_kind or
            mapping.get("road_sha256") != sha(bundle / "crest.xodr") or
            mapping.get("legal_verdict") is not None):
        raise ValueError("Original generated map receipt")
    for name, lane_id in (("west_500ft", 1), ("ego_approach", -1),
                          ("crest", -1), ("east_500ft", -1)):
        waypoint = mapping.get("lane_readback", {}).get(name)
        if waypoint is None or waypoint.get("road_id") != 407 or \
                waypoint.get("lane_id") != lane_id or "Driving" not in waypoint.get("lane_type", "") or \
                len(waypoint.get("native_xyz_m", [])) != 3 or \
                not all(map(finite, waypoint["native_xyz_m"])):
            raise ValueError("Original generated crest lane readback")
    if (report.get("case_id") != cfg["case_id"] or report.get("candidate_id") != cfg["candidate_id"] or
            report.get("config_sha256") != sha(bundle / "config.json") or
            report.get("requested_frames") != FRAMES or report.get("observed_frames") != FRAMES or
            report.get("error") is not None or report.get("restoration", {}).get("restored") is not True or
            report.get("accepted") is not False or report.get("delivery_ready") is not False):
        raise ValueError("Original capture or restoration receipt")
    media = {name + ".mkv": (sha(directory / (name + ".mkv")) if synthetic_fixture else
             ffv1_frames(directory / (name + ".mkv"))) for name in CAMERAS}
    if (review.get("format") != "c104496-original-human-review-v1" or
            review.get("source_kind") != expected_review_kind or
            not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"].strip() or
            review.get("case_id") != cfg["case_id"] or review.get("candidate_id") != cfg["candidate_id"] or
            review.get("raw_sha256") != sha(raw_path) or review.get("video_frames_sha256") != sha(video_path) or
            review.get("map_sha256") != sha(map_path) or review.get("capture_report_sha256") != sha(capture_path) or
            review.get("media_sha256") != media):
        raise ValueError("Original human review provenance")
    frame_reviews = review.get("turn_frame_visibility")
    if not isinstance(frame_reviews, dict):
        raise ValueError("Human turn-frame visibility missing")
    first_native = raw[0].get("native_frame")
    if type(first_native) is not int:
        raise ValueError("Native frame origin missing")
    ids = {"ego": set(), "other": set()}
    prior = {}
    turn_count = reviewed_count = clear_both = blocked_either = 0
    human_both_visible = human_either_not_visible = 0
    reverse_motion = opposite_heading = 0
    for i, (request, observed, image) in enumerate(zip(requests, raw, video)):
        if (request.get("frame") != i or observed.get("frame") != i or image.get("video_frame") != i or
                observed.get("request_frame") != i or observed.get("native_frame") != first_native+i or
                image.get("native_frame") != first_native+i or
                observed.get("source_kind") != expected_kind or
                not finite(observed.get("time_s")) or not finite(image.get("time_s")) or
                abs(observed["time_s"] - (i+1)/RATE) > .005 or
                abs(image["time_s"] - observed["time_s"]) > 1e-6 or
                observed.get("requested_motion_phase") != request["requested_motion_phase"] or
                observed.get("human_visibility_reviewed") is not False or
                observed.get("legal_verdict") is not None):
            raise ValueError("Original request/actor/video frame join")
        for key, blueprint in (("ego", cfg["ego_blueprint"]),
                               ("other", cfg["other_vehicle_blueprint"])):
            center, velocity, _ = actor(observed.get(key, {}), blueprint)
            ids[key].add(observed[key]["actor_id"])
            if key in prior and math.dist(center, prior[key]) > observed[key]["speed_mps"]/RATE + .5:
                raise ValueError("Original speed/displacement discontinuity")
            prior[key] = center
        if observed.get("ego_road_id") not in (407, None):
            raise ValueError("Original ego road changed")
        yaw = math.radians(observed["ego"]["yaw_deg"])
        velocity = observed["ego"]["velocity_native_xyz_mps"]
        longitudinal = velocity[0]*math.cos(yaw) + velocity[1]*math.sin(yaw)
        reverse_motion += request["requested_motion_phase"] == "reverse_right" and longitudinal < -.3
        opposite_heading += request["requested_motion_phase"] == "opposite_direction" and math.cos(yaw) < -.8
        stations = observed.get("observer_stations_m")
        rays = observed.get("body_rays_by_approach")
        if not isinstance(stations, list) or len(stations) != 2 or \
                not isinstance(rays, list) or len(rays) != 2:
            raise ValueError("Original observer/ray structure")
        body_points = observed["ego"]["body_native_xyz_m"]
        body_center = [sum(point[axis] for point in body_points)/8 for axis in range(3)]
        for station, approach_rays in zip(stations, rays):
            if station is None:
                if approach_rays is not None: raise ValueError("Ray without 500-foot observer")
                continue
            if not finite(station) or not 0 <= station <= 450 or \
                    abs(roadway_distance(station, observed["ego"]["center_native_xyz_m"][0],
                                         cfg["grade_height_m"]) - 152.4) > .05 or \
                    not isinstance(approach_rays, list) or len(approach_rays) != 9:
                raise ValueError("Original 500-foot body rays")
            for ray_index, ray in enumerate(approach_rays):
                if (type(ray.get("clear")) is not bool or
                        not isinstance(ray.get("blockers"), list) or
                        ray["clear"] != (len(ray["blockers"]) == 0) or
                        any(not isinstance(ray.get(key), list) or len(ray[key]) != 3 or
                            not all(map(finite, ray[key])) for key in ("eye_m", "body_sample_m"))):
                    raise ValueError("Original ray sample inconsistent")
                expected_target = body_points[ray_index] if ray_index < 8 else body_center
                if math.dist(ray["body_sample_m"], expected_target) > .03 or \
                        abs(ray["eye_m"][0] - station) > 2.5:
                    raise ValueError("Original nine body samples or observer station changed")
        if request["requested_motion_phase"] in TURN_PHASES:
            turn_count += 1
            frame_review = frame_reviews.get(str(i))
            if not isinstance(frame_review, dict) or \
                    type(frame_review.get("west_visible")) is not bool or \
                    type(frame_review.get("east_visible")) is not bool:
                raise ValueError("Missing original reviewed turn frame")
            reviewed_count += 1
            human_both_visible += frame_review["west_visible"] and frame_review["east_visible"]
            human_either_not_visible += not (frame_review["west_visible"] and frame_review["east_visible"])
            if any(approach is None for approach in rays):
                raise ValueError("Turn frame missing 500-foot body rays")
            ray_clear = [any(sample["clear"] for sample in approach) for approach in rays]
            clear_both += all(ray_clear)
            blocked_either += not all(ray_clear)
    if (any(len(value) != 1 for value in ids.values()) or
            mapping.get("ego_actor_id") not in ids["ego"] or
            mapping.get("other_actor_id") not in ids["other"] or
            next(iter(ids["ego"])) == next(iter(ids["other"]))):
        raise ValueError("Original actor identity continuity")
    return {"format": "c104496-original-saved-measurement-v1", "case_id": checked["case_id"],
            "candidate_id": checked["candidate"],
            "source_kind": "synthetic_fixture" if synthetic_fixture else "original_native",
            "frames_joined": FRAMES, "turn_frames": turn_count, "reviewed_turn_frames": reviewed_count,
            "ray_clear_from_both_turn_frames": clear_both,
            "ray_blocked_from_either_turn_frames": blocked_either,
            "human_both_visible_turn_frames": human_both_visible,
            "human_either_not_visible_turn_frames": human_either_not_visible,
            "observed_reverse_motion_frames": reverse_motion,
            "observed_opposite_heading_frames": opposite_heading,
            "raw_sha256": sha(raw_path), "review_sha256": sha(review_path),
            "human_recognition_established": False, "original_native_observed": not synthetic_fixture,
            "legal_verdict": None,
            "accepted": False, "delivery_ready": False}


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
