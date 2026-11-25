"""Independent source-only comparison of following traffic response.

This checks Native-shaped actor observations. It makes no legal impediment
finding and a synthetic fixture does not establish physical road behavior.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(raw_path, frame_path, review_path):
    raw_path, frame_path, review_path = map(Path, (raw_path, frame_path, review_path))
    actors, frames = source_rows(raw_path), source_rows(frame_path)
    review = json.loads(review_path.read_text())
    if len(actors) != FRAMES or len(frames) != FRAMES:
        raise ValueError("Traffic audit requires 600 joined source frames")
    if review.get("raw_sha256") != sha(raw_path) or review.get("video_frames_sha256") != sha(frame_path):
        raise ValueError("Traffic review source hash differs")
    if review.get("source_kind") not in ("synthetic_fixture", "original_native_review"):
        raise ValueError("Traffic review source kind absent")
    if not isinstance(review.get("case_id"), str) or not review["case_id"].startswith(
            "training__C109137__NRS-484B-217-2__motor_vehicle_driver__traffic_"):
        raise ValueError("Traffic review exact case identity absent")
    identity = None
    crossing = None
    adjoining = None
    signal = None
    following_speed = []
    oncoming_speed = []
    previous_following = None
    first_native = actors[0].get("native_frame")
    if type(first_native) is not int:
        raise ValueError("Traffic Native frame origin absent")
    for i, (row, frame) in enumerate(zip(actors, frames)):
        if (row.get("frame") != i or frame.get("video_frame") != i or
                row.get("native_frame") != first_native + i or
                frame.get("native_frame") != first_native + i or
                not math.isclose(row.get("time_s", -1), (i + 1) / RATE, abs_tol=.005) or
                not math.isclose(row.get("time_s", -1), frame.get("time_s", -2), abs_tol=1e-6)):
            raise ValueError("Traffic Native/video frame join differs")
        if row.get("source_kind") != review["source_kind"]:
            raise ValueError("Traffic observed source provenance differs")
        following, oncoming, ego = (row.get(k, {}) for k in ("following", "oncoming", "ego"))
        pair = (following.get("actor_id"), oncoming.get("actor_id"), ego.get("actor_id"))
        if any(type(x) is not int for x in pair) or len(set(pair)) != 3:
            raise ValueError("Traffic participant identity absent")
        if identity is None:
            identity = pair
        elif pair != identity:
            raise ValueError("Traffic participant identity changed")
        for participant, speeds in ((following, following_speed), (oncoming, oncoming_speed)):
            velocity = participant.get("velocity_native_xyz_mps")
            speed = participant.get("speed_mps")
            if (not isinstance(velocity, list) or len(velocity) != 3 or
                    not all(type(v) in (int, float) and math.isfinite(v) for v in velocity) or
                    type(speed) not in (int, float) or not math.isfinite(speed) or
                    abs(math.dist([0, 0, 0], velocity) - speed) > .02):
                raise ValueError("Traffic observed velocity absent or inconsistent")
            speeds.append(speed)
        position = following.get("center_native_xyz_m")
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError("Following actor position absent")
        if previous_following is not None and math.dist(position, previous_following) > following_speed[-1] / RATE + .5:
            raise ValueError("Following actor motion inconsistent with speed")
        previous_following = position
        body = ego.get("body_native_xyz_m")
        if not isinstance(body, list) or len(body) != 8 or any(len(v) != 3 for v in body):
            raise ValueError("Observed ego body absent")
        if crossing is None and min(v[1] for v in body) <= 0 <= max(v[1] for v in body) and max(v[0] for v in body) >= 0 and min(v[0] for v in body) <= 55:
            crossing = i
        if adjoining is None and row.get("observed_road_id") == 218 and row.get("observed_lane_id") == -1:
            adjoining = i
        if signal is None and row.get("observed_left_indicator") is True:
            signal = i
    if crossing is None or adjoining is None:
        raise ValueError("Observed crossing or adjoining-road entry absent")
    if crossing < 40 or crossing + 60 >= FRAMES:
        raise ValueError("Traffic response windows unavailable")
    before = sum(following_speed[crossing - 40:crossing]) / 40
    after = min(following_speed[crossing + 20:crossing + 60])
    return {
        "case_id": review.get("case_id"),
        "candidate_id": review.get("candidate_id"),
        "source_kind": review["source_kind"],
        "raw_sha256": sha(raw_path),
        "frame_map_sha256": sha(frame_path),
        "review_sha256": sha(review_path),
        "first_stripe_body_frame": crossing,
        "first_adjoining_road_frame": adjoining,
        "first_left_indicator_frame": signal,
        "following_pre_crossing_mean_speed_mps": round(before, 5),
        "following_post_crossing_min_speed_mps": round(after, 5),
        "following_speed_drop_mps": round(before - after, 5),
        "oncoming_pre_crossing_mean_speed_mps": round(sum(oncoming_speed[crossing - 40:crossing]) / 40, 5),
        "oncoming_post_crossing_min_speed_mps": round(min(oncoming_speed[crossing + 20:crossing + 60]), 5),
        "legal_impediment_determined": False,
        "physical_completion_claimed": False,
    }


def compare(clear, response):
    fixed = ("first_stripe_body_frame", "first_adjoining_road_frame",
             "first_left_indicator_frame", "oncoming_pre_crossing_mean_speed_mps",
             "oncoming_post_crossing_min_speed_mps")
    for key in fixed:
        if clear[key] != response[key]:
            raise ValueError("Traffic comparison changed fixed condition: " + key)
    if (clear["case_id"] != "training__C109137__NRS-484B-217-2__motor_vehicle_driver__traffic_clear_traffic" or
            response["case_id"] != "training__C109137__NRS-484B-217-2__motor_vehicle_driver__traffic_following_brake" or
            clear["candidate_id"] != response["candidate_id"] or
            clear["source_kind"] != response["source_kind"]):
        raise ValueError("Traffic comparison case/candidate identity differs")
    if response["following_speed_drop_mps"] <= clear["following_speed_drop_mps"]:
        raise ValueError("Traffic comparison response difference absent")
    return {"format": "c109137-source-traffic-comparison-v1", "clear": clear,
            "response": response, "deliberate_difference": "observed following speed response",
            "legal_impediment_determined": False, "physical_completion_claimed": False,
            "passed": True}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("clear_raw", type=Path)
    ap.add_argument("clear_frames", type=Path)
    ap.add_argument("clear_review", type=Path)
    ap.add_argument("response_raw", type=Path)
    ap.add_argument("response_frames", type=Path)
    ap.add_argument("response_review", type=Path)
    a = ap.parse_args()
    print(json.dumps(compare(measure(a.clear_raw, a.clear_frames, a.clear_review),
                             measure(a.response_raw, a.response_frames, a.response_review)),
                     indent=2, allow_nan=False))
