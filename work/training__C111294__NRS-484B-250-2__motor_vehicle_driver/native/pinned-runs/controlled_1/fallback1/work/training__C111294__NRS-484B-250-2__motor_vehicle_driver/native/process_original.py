"""Source-bound processing of an unaccepted original C111294 capture."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from build import FRAMES, RATE
from check import check

CAMERAS = ("ego_view", "other_view", "overview")
LANES = {"ego_approach": 250, "ego_connector": 251, "ego_departure": 252,
         "other_approach": 253, "other_connector": 254, "other_departure": 255}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(number):
    return type(number) in (int, float) and math.isfinite(number)


def media_hash(path, synthetic_fixture):
    path = Path(path)
    if synthetic_fixture:
        if not path.is_file() or path.read_bytes() != b"C111294 SYNTHETIC FIXTURE; NOT VIDEO\n":
            raise ValueError("Synthetic fixture media changed")
    else:
        try:
            run = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                  "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", str(path)],
                                 capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise ValueError("ffprobe unavailable for original media") from exc
        if run.returncode:
            raise ValueError("Original camera media unreadable")
        streams = json.loads(run.stdout).get("streams", [])
        if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
                streams[0].get("nb_read_frames") != str(FRAMES):
            raise ValueError("Original FFV1 frame contract")
    return sha(path)


def actor(row, blueprint):
    if row.get("blueprint") != blueprint or type(row.get("actor_id")) is not int:
        raise ValueError("Actor identity or blueprint")
    center, velocity, body = (row.get(key) for key in
                              ("center_native_xyz_m", "velocity_native_xyz_mps", "body_native_xyz_m"))
    if (not isinstance(center, list) or len(center) != 3 or not all(map(finite, center)) or
            not isinstance(velocity, list) or len(velocity) != 3 or not all(map(finite, velocity)) or
            not isinstance(body, list) or len(body) != 8 or
            any(not isinstance(p, list) or len(p) != 3 or not all(map(finite, p)) for p in body) or
            not finite(row.get("yaw_deg")) or not finite(row.get("speed_mps")) or
            abs(row["speed_mps"] - math.sqrt(sum(v*v for v in velocity))) > .02 or
            math.dist(center, [sum(p[k] for p in body)/8 for k in range(3)]) > 1.0):
        raise ValueError("Actor body or velocity contract")
    return center, body


def process(bundle, directory, review_path, *, synthetic_fixture=False):
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw_path, video_path = directory / "native-raw-actors.jsonl", directory / "video_frames.jsonl"
    map_path, report_path = directory / "native-map-readback.json", directory / "native-capture-report.json"
    requests, raw, video = lines(bundle / "requested-tracks.jsonl"), lines(raw_path), lines(video_path)
    mapping, report, review = (json.loads(path.read_text()) for path in (map_path, report_path, review_path))
    if any(len(rows) != FRAMES for rows in (requests, raw, video)):
        raise ValueError("Exactly 600 request, actor and video frames required")
    kind = "synthetic_fixture" if synthetic_fixture else "original_native"
    review_kind = "synthetic_fixture_review" if synthetic_fixture else "original_native_review"
    if (mapping.get("source_kind") != kind or mapping.get("road_sha256") != sha(bundle / "crossroads.xodr") or
            mapping.get("junction_id") != 1 or mapping.get("authored_signal_count") != 0 or
            not isinstance(mapping.get("native_map_sha256"), str) or
            len(mapping["native_map_sha256"]) != 64 or mapping.get("legal_verdict") is not None):
        raise ValueError("Generated map receipt mismatch")
    for name, road_id in LANES.items():
        lane = mapping.get("lane_readback", {}).get(name, {})
        if (lane.get("road_id") != road_id or lane.get("lane_id") != -1 or
                "Driving" not in lane.get("lane_type", "") or
                not isinstance(lane.get("native_xyz_m"), list) or
                len(lane["native_xyz_m"]) != 3 or not all(map(finite, lane["native_xyz_m"]))):
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
    if (review.get("format") != "c111294-2502-original-review-v1" or
            review.get("source_kind") != review_kind or
            not isinstance(review.get("reviewer_id"), str) or not review["reviewer_id"].strip() or
            review.get("case_id") != cfg["case_id"] or review.get("candidate_id") != cfg["candidate_id"] or
            review.get("raw_sha256") != sha(raw_path) or
            review.get("video_frames_sha256") != sha(video_path) or
            review.get("map_sha256") != sha(map_path) or
            review.get("capture_report_sha256") != sha(report_path) or
            review.get("media_sha256") != media or
            any(type(review.get(key)) is not bool for key in
                ("right_side_other_visible", "official_device_governance_reviewed",
                 "yield_sequence_visible", "opposite_direction_left_turn_exclusion_reviewed",
                 "subsection4_reviewed"))):
        raise ValueError("Source-hashed visual review receipt mismatch")
    first_native = raw[0].get("native_frame")
    if type(first_native) is not int:
        raise ValueError("Native frame origin missing")
    ids, previous = {"ego": set(), "other": set()}, {}
    entries, exits = {"ego": None, "other": None}, {"ego": None, "other": None}
    for i, (request, observed, image) in enumerate(zip(requests, raw, video)):
        t = (i+1)/RATE
        if (request.get("frame") != i or observed.get("frame") != i or
                observed.get("request_frame") != i or image.get("video_frame") != i or
                observed.get("native_frame") != first_native+i or
                image.get("native_frame") != first_native+i or
                observed.get("source_kind") != kind or
                not finite(observed.get("time_s")) or not finite(image.get("time_s")) or
                abs(observed["time_s"]-t) > .005 or
                abs(image["time_s"]-observed["time_s"]) > 1e-6 or
                observed.get("requested_ego_phase") != request["requested_ego_phase"] or
                observed.get("authored_official_device_count") != 0 or
                observed.get("legal_verdict") is not None):
            raise ValueError("Request, actor and video frame join mismatch")
        for key, blueprint, axis in (("ego", cfg["ego_blueprint"], 0),
                                     ("other", cfg["other_blueprint"], 1)):
            center, body = actor(observed.get(key, {}), blueprint)
            ids[key].add(observed[key]["actor_id"])
            if key in previous and math.dist(center, previous[key]) > \
                    max(observed[key]["speed_mps"], raw[i-1][key]["speed_mps"])/RATE + .5:
                raise ValueError("Actor displacement discontinuity")
            previous[key] = center
            if entries[key] is None and max(p[axis] for p in body) >= -20:
                entries[key] = t
            if exits[key] is None and min(p[axis] for p in body) >= 20:
                exits[key] = t
        if observed.get("ego_road_id") not in (250, 251, 252, None) or \
                observed.get("other_road_id") not in (253, 254, 255, None):
            raise ValueError("Actor crossed to unexpected road")
    if (any(len(value) != 1 for value in ids.values()) or
            mapping.get("ego_actor_id") not in ids["ego"] or
            mapping.get("other_actor_id") not in ids["other"] or
            next(iter(ids["ego"])) == next(iter(ids["other"])) or
            any(value is None for value in (*entries.values(), *exits.values()))):
        raise ValueError("Actor continuity or intersection traversal missing")
    gap = round(entries["ego"]-entries["other"], 6)
    return {"format": "c111294-2502-original-saved-v1", "case_id": cfg["case_id"],
            "candidate_id": cfg["candidate_id"], "source_kind": kind,
            "frames_joined": FRAMES, "ego_front_entry_s": entries["ego"],
            "other_front_entry_s": entries["other"], "ego_rear_exit_s": exits["ego"],
            "other_rear_exit_s": exits["other"], "ego_minus_other_front_entry_s": gap,
            "raw_sha256": sha(raw_path), "review_sha256": sha(review_path),
            "approximate_same_time_legally_determined": False,
            "right_of_way_legally_determined": False,
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
