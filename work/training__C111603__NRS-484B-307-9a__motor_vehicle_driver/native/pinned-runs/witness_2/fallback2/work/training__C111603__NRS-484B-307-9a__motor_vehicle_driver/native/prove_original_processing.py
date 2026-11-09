"""CPU source-shape proof for C111603 original processing using marker media."""
import json
import math
from pathlib import Path
import tempfile

from process_original import CAMERAS, FIXTURE_MEDIA, LANES, REVIEW_FLAGS, process, sha


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def write_rows(path, value):
    path.write_text("".join(json.dumps(row) + "\n" for row in value))


def actor(actor_id, blueprint, point, previous, heading):
    velocity = [(point[k] - previous[k]) * 20 for k in range(3)]
    body = [[point[0] + dx, point[1] + dy, point[2] + dz]
            for dx in (-1, 1) for dy in (-.4, .4) for dz in (-.5, .5)]
    return {"actor_id": actor_id, "blueprint": blueprint,
            "center_native_xyz_m": point, "yaw_deg": heading,
            "velocity_native_xyz_mps": velocity,
            "speed_mps": math.sqrt(sum(v*v for v in velocity)),
            "body_native_xyz_m": body}


def fixture(bundle, directory):
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in
                (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    write(directory / "native-map-readback.json", {
        "source_kind": "synthetic_fixture",
        "road_sha256": sha(bundle / "arrow-intersection.xodr"),
        "native_map_sha256": "a" * 64,
        "lane_readback": {name: {"road_id": road, "lane_id": lane,
                                 "native_xyz_m": [0.0, 0.0, 0.0]}
                          for name, (road, lane) in LANES.items()},
        "red_actor_id": 601, "arrow_actor_id": 1603,
        "ego_actor_id": 99, "other_actor_id": 100,
        "directional_arrow_pixels_verified": False,
        "signal_governs_ego_verified": False,
        "other_traffic_lawfulness_verified": False,
        "legal_verdict": None})
    write(directory / "native-capture-report.json", {
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "config_sha256": sha(bundle / "config.json"),
        "requested_frames": 480, "observed_frames": 480,
        "restoration": {"restored": True}, "error": None,
        "accepted": False, "delivery_ready": False, "legal_verdict": None})
    raw, video = [], []
    for i, request in enumerate(requests):
        ego_point = request["requested_ego_xyz_m"]
        other_point = request["requested_other_vehicle_xyz_m"]
        ego_prev = requests[max(0, i - 1)]["requested_ego_xyz_m"]
        other_prev = requests[max(0, i - 1)]["requested_other_vehicle_xyz_m"]
        raw.append({"frame": i, "native_frame": 1000 + i,
                    "time_s": (i + 1) / 20, "source_kind": "synthetic_fixture",
                    "request_frame": i,
                    "ego": actor(99, cfg["ego_blueprint"], ego_point, ego_prev,
                                 math.degrees(request["requested_heading_rad"])),
                    "other_vehicle": actor(100, cfg["other_blueprint"], other_point,
                                           other_prev, 0.0),
                    "red_actor_id": 601, "red_state": "Red",
                    "arrow_actor_id": 1603, "arrow_state": "Green",
                    "requested_phase": request["requested_phase"],
                    "directional_arrow_pixels_verified": False,
                    "signal_governs_ego_verified": False,
                    "other_traffic_lawfulness_verified": False,
                    "legal_verdict": None})
        video.append({"video_frame": i, "native_frame": 1000 + i,
                      "time_s": (i + 1) / 20})
    write_rows(directory / "native-raw-actors.jsonl", raw)
    write_rows(directory / "video_frames.jsonl", video)
    media = {}
    for camera in CAMERAS:
        path = directory / (camera + ".mkv")
        path.write_bytes(FIXTURE_MEDIA)
        media[path.name] = sha(path)
    review_path = directory / "review.json"
    write(review_path, {
        "format": "c111603-3079a-original-review-v1",
        "source_kind": "synthetic_fixture_review", "reviewer_id": "cpu-fixture-only",
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "raw_sha256": sha(directory / "native-raw-actors.jsonl"),
        "video_frames_sha256": sha(directory / "video_frames.jsonl"),
        "map_sha256": sha(directory / "native-map-readback.json"),
        "capture_report_sha256": sha(directory / "native-capture-report.json"),
        "media_sha256": media,
        **{flag: False for flag in REVIEW_FLAGS}})
    return review_path


def refresh_review(directory, review_path):
    data = json.loads(review_path.read_text())
    for key, path in (("raw_sha256", "native-raw-actors.jsonl"),
                      ("video_frames_sha256", "video_frames.jsonl"),
                      ("map_sha256", "native-map-readback.json"),
                      ("capture_report_sha256", "native-capture-report.json")):
        data[key] = sha(directory / path)
    data["media_sha256"] = {name + ".mkv": sha(directory / (name + ".mkv"))
                            for name in CAMERAS}
    write(review_path, data)


def change_json(path, change):
    data = json.loads(path.read_text())
    change(data)
    write(path, data)


def change_line(path, index, change):
    data = [json.loads(line) for line in path.read_text().splitlines()]
    change(data[index])
    write_rows(path, data)


def prove(bundle):
    bundle = Path(bundle)
    with tempfile.TemporaryDirectory(prefix="c111603-shape-") as name:
        directory = Path(name)
        review = fixture(bundle, directory)
        measured = process(bundle, directory, review, synthetic_fixture=True)
        assert measured["frames_joined"] == 480
        assert measured["observed_movement_matches_request"]
        assert not measured["original_native_observed"] and not measured["delivery_ready"]
        negatives = []

        def rejected(label, edit, *, rehash=False):
            before = {path: path.read_bytes() for path in directory.iterdir() if path.is_file()}
            try:
                edit()
                if rehash:
                    refresh_review(directory, review)
                try:
                    process(bundle, directory, review, synthetic_fixture=True)
                except ValueError:
                    negatives.append(label)
                else:
                    raise AssertionError("Changed original-shape input accepted: " + label)
            finally:
                for path, raw in before.items():
                    path.write_bytes(raw)

        rejected("ego_actor_identity", lambda: change_line(
            directory / "native-raw-actors.jsonl", 10,
            lambda row: row["ego"].update(actor_id=98)), rehash=True)
        rejected("other_actor_identity", lambda: change_line(
            directory / "native-raw-actors.jsonl", 10,
            lambda row: row["other_vehicle"].update(actor_id=101)), rehash=True)
        rejected("video_frame", lambda: change_line(
            directory / "video_frames.jsonl", 10,
            lambda row: row.update(video_frame=11)), rehash=True)
        rejected("body_vertex", lambda: change_line(
            directory / "native-raw-actors.jsonl", 10,
            lambda row: row["ego"]["body_native_xyz_m"][0].__setitem__(0, 100)), rehash=True)
        rejected("generated_lane", lambda: change_json(
            directory / "native-map-readback.json",
            lambda row: row["lane_readback"]["south_approach"].update(road_id=2)), rehash=True)
        rejected("signal_state", lambda: change_line(
            directory / "native-raw-actors.jsonl", 10,
            lambda row: row.update(arrow_state="Red")), rehash=True)
        rejected("media", lambda: (directory / "overview.mkv").write_bytes(b"altered"),
                 rehash=True)
        rejected("review_digest", lambda: change_json(
            review, lambda row: row.update(raw_sha256="0" * 64)))
        try:
            process(bundle, directory, review)
        except ValueError:
            negatives.append("fixture_rejected_as_original")
        else:
            raise AssertionError("Synthetic media accepted as original FFV1")
        return {"case_id": measured["case_id"], "candidate_id": measured["candidate_id"],
                "positive_count": 1, "negative_count": len(negatives),
                "negative_names": negatives,
                "observed_heading_change_deg": measured["observed_heading_change_deg"],
                "observed_movement_matches_request": True,
                "synthetic_fixture_only": True, "original_native_observed": False,
                "delivery_ready": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.bundle), sort_keys=True))
