"""Synthetic source-shape positives and material negatives for original-mode processor."""
import copy
import json
import math
import tempfile
from pathlib import Path

from build import CASES, HERE, RATE, elevation, put, sha
from process_original import process
from saved import observer_station, ray_margin


def box(center):
    x, y, z = center
    return [[x+dx, y+dy, z+dz] for dx in (-2, 2) for dy in (-.9, .9) for dz in (-.7, .7)]


def actor(center, previous, frame, blueprint, actor_id, yaw):
    velocity = [0, 0, 0] if previous is None else [(center[i]-previous[i])*RATE for i in range(3)]
    return {"actor_id": actor_id, "blueprint": blueprint, "center_native_xyz_m": center,
            "yaw_deg": yaw, "velocity_native_xyz_mps": velocity,
            "speed_mps": math.sqrt(sum(v*v for v in velocity)), "body_native_xyz_m": box(center)}


def fixture(bundle, directory):
    bundle, directory = Path(bundle), Path(directory)
    cfg = json.loads((bundle / "config.json").read_text())
    height = cfg["grade_height_m"]
    requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    raw, video, reviews = [], [], {}
    previous_ego = previous_other = None
    for i, request in enumerate(requests):
        center = request["requested_ego_xyz_m"]
        other_center = request["requested_other_vehicle_xyz_m"]
        ego = actor(center, previous_ego, i, cfg["ego_blueprint"], 10,
                    math.degrees(request["requested_heading_rad"]))
        other = actor(other_center, previous_other, i, cfg["other_vehicle_blueprint"], 11, 0)
        previous_ego, previous_other = center, other_center
        stations = [observer_station(center[0], height, direction) for direction in (-1, 1)]
        rays = []
        clears = []
        for station, lane_y in zip(stations, (1.75, -1.75)):
            if station is None:
                rays.append(None); clears.append(False); continue
            clear = ray_margin(center[0], station, height) <= 0
            clears.append(clear)
            eye = [station, lane_y, elevation(station, height)+1.4]
            points = ego["body_native_xyz_m"]
            points = points + [[sum(p[axis] for p in points)/8 for axis in range(3)]]
            rays.append([{"eye_m": eye, "body_sample_m": point, "clear": clear,
                          "blockers": [] if clear else [{"label": "synthetic_grade",
                              "location_m": [(eye[k]+point[k])/2 for k in range(3)]}]}
                         for point in points])
        if request["requested_motion_phase"] in ("forward_left", "reverse_right", "forward_left_finish"):
            reviews[str(i)] = {"west_visible": clears[0], "east_visible": clears[1]}
        raw.append({"frame": i, "native_frame": 1000+i, "time_s": (i+1)/RATE,
                    "source_kind": "synthetic_fixture", "request_frame": i,
                    "ego": ego, "other": other, "ego_road_id": 407, "ego_lane_id": -1,
                    "observer_stations_m": stations, "body_rays_by_approach": rays,
                    "requested_motion_phase": request["requested_motion_phase"],
                    "human_visibility_reviewed": False, "legal_verdict": None})
        video.append({"video_frame": i, "native_frame": 1000+i, "time_s": (i+1)/RATE})
    directory.mkdir(parents=True)
    (directory / "native-raw-actors.jsonl").write_text("".join(json.dumps(row) + "\n" for row in raw))
    (directory / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in video))
    for name in ("west_view", "east_view", "overview"):
        (directory / (name + ".mkv")).write_bytes(b"synthetic fixture; not FFV1\n")
    mapping = {"source_kind": "synthetic_fixture", "road_sha256": sha(bundle / "crest.xodr"),
               "legal_verdict": None, "ego_actor_id": 10, "other_actor_id": 11,
               "lane_readback": {name: {"road_id": 407, "lane_id": lane,
                     "lane_type": "Driving", "native_xyz_m": [station, 0, elevation(station, height)]}
                    for name, lane, station in (("west_500ft", 1, 47.6), ("ego_approach", -1, 180),
                                               ("crest", -1, 200), ("east_500ft", -1, 352.4))}}
    put(directory / "native-map-readback.json", mapping)
    report = {"case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
              "config_sha256": sha(bundle / "config.json"), "requested_frames": 700,
              "observed_frames": 700, "error": None, "restoration": {"restored": True},
              "accepted": False, "delivery_ready": False}
    put(directory / "native-capture-report.json", report)
    review = {"format": "c104496-original-human-review-v1", "source_kind": "synthetic_fixture_review",
              "reviewer_id": "synthetic-fixture", "case_id": cfg["case_id"],
              "candidate_id": cfg["candidate_id"], "turn_frame_visibility": reviews}
    refresh(directory, review)
    return directory / "review.json"


def refresh(directory, review):
    review["raw_sha256"] = sha(directory / "native-raw-actors.jsonl")
    review["video_frames_sha256"] = sha(directory / "video_frames.jsonl")
    review["map_sha256"] = sha(directory / "native-map-readback.json")
    review["capture_report_sha256"] = sha(directory / "native-capture-report.json")
    review["media_sha256"] = {name + ".mkv": sha(directory / (name + ".mkv"))
                              for name in ("west_view", "east_view", "overview")}
    put(directory / "review.json", review)


def prove():
    positives = negatives = 0
    metrics = {}
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in CASES:
            bundle = HERE / "drafts" / suffix / "primary"
            directory = Path(tmp) / suffix
            review_path = fixture(bundle, directory)
            saved = process(bundle, directory, review_path, synthetic_fixture=True)
            if saved["frames_joined"] != 700 or saved["source_kind"] != "synthetic_fixture" or \
                    saved["delivery_ready"] or saved["original_native_observed"]:
                raise AssertionError("Synthetic source-shape positive invalid")
            positives += 1
            metrics[suffix] = {key: saved[key] for key in ("turn_frames", "ray_clear_from_both_turn_frames",
                           "ray_blocked_from_either_turn_frames", "observed_reverse_motion_frames")}
            try:
                process(bundle, directory, review_path)
            except ValueError:
                negatives += 1
            else:
                raise AssertionError("Synthetic fixture accepted as original")
            original_raw = (directory / "native-raw-actors.jsonl").read_text()
            original_review = json.loads(review_path.read_text())
            for name in ("frame_join", "actor_identity", "ray_consistency", "road_distance"):
                rows = [json.loads(x) for x in original_raw.splitlines()]
                if name == "frame_join": rows[100]["native_frame"] += 2
                elif name == "actor_identity": rows[100]["ego"]["actor_id"] = 99
                elif name == "ray_consistency": rows[100]["body_rays_by_approach"][0][0]["clear"] = not rows[100]["body_rays_by_approach"][0][0]["clear"]
                else: rows[100]["observer_stations_m"][0] += 2
                (directory / "native-raw-actors.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
                refresh(directory, copy.deepcopy(original_review))
                try:
                    process(bundle, directory, review_path, synthetic_fixture=True)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Rehashed semantic negative accepted: " + name)
                (directory / "native-raw-actors.jsonl").write_text(original_raw)
                refresh(directory, copy.deepcopy(original_review))
            review = copy.deepcopy(original_review)
            review["turn_frame_visibility"].pop(next(iter(review["turn_frame_visibility"])))
            refresh(directory, review)
            try:
                process(bundle, directory, review_path, synthetic_fixture=True)
            except ValueError:
                negatives += 1
            else:
                raise AssertionError("Missing reviewed turn frame accepted")
    proof = {"format": "c104496-original-shape-synthetic-proof-v1", "positives": positives,
             "negatives": negatives, "metrics": metrics, "synthetic_fixture_only": True,
             "original_native_executed": False, "delivery_ready": False}
    put(HERE / "original-shape-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove()))
