"""CPU proof of the original-capture processor with an explicitly synthetic fixture."""
import json
import math
from pathlib import Path
import tempfile

from process_original import CAMERAS, FIXTURE_MEDIA, LANES, process, sha

HERE = Path(__file__).resolve().parent


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def write_rows(path, data):
    path.write_text("".join(json.dumps(row) + "\n" for row in data))


def fixture(bundle, directory):
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    lane_readback = {
        name: {"road_id": road, "lane_id": lane, "lane_type": "Driving",
               "native_xyz_m": [0.0, 0.0, 0.0]}
        for name, (road, lane) in LANES.items()}
    write_json(directory / "native-map-readback.json", {
        "source_kind": "synthetic_fixture",
        "road_sha256": sha(bundle / "district-crossroads.xodr"),
        "native_map_sha256": "a" * 64, "lane_readback": lane_readback,
        "junction_id": 1, "ego_actor_id": 99,
        "authored_business_district": True,
        "district_designation_verified": False, "legal_verdict": None})
    write_json(directory / "native-capture-report.json", {
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "config_sha256": sha(bundle / "config.json"),
        "requested_frames": 800, "observed_frames": 800,
        "restoration": {"restored": True}, "error": None,
        "accepted": False, "delivery_ready": False, "legal_verdict": None})
    raw, video = [], []
    for i, request in enumerate(requests):
        point = request["requested_ego_xyz_m"]
        prev = requests[max(0, i - 1)]["requested_ego_xyz_m"]
        velocity = [(point[k] - prev[k]) * 20 for k in range(3)]
        body = [[point[0] + dx, point[1] + dy, point[2] + dz]
                for dx in (-1, 1) for dy in (-.4, .4) for dz in (-.5, .5)]
        raw.append({"frame": i, "native_frame": 1000 + i, "time_s": (i + 1)/20,
                    "source_kind": "synthetic_fixture", "request_frame": i,
                    "ego": {"actor_id": 99, "blueprint": cfg["ego_blueprint"],
                            "center_native_xyz_m": point,
                            "yaw_deg": math.degrees(request["requested_heading_rad"]),
                            "velocity_native_xyz_mps": velocity,
                            "speed_mps": math.sqrt(sum(v*v for v in velocity)),
                            "body_native_xyz_m": body},
                    "ego_road_id": 403 if point[0] < -20 else 404 if point[0] <= 20 else 405,
                    "requested_phase": request["requested_phase"],
                    "authored_business_district": True,
                    "district_designation_verified": False, "legal_verdict": None})
        video.append({"video_frame": i, "native_frame": 1000+i, "time_s": (i+1)/20})
    write_rows(directory / "native-raw-actors.jsonl", raw)
    write_rows(directory / "video_frames.jsonl", video)
    media = {}
    for camera in CAMERAS:
        path = directory / (camera + ".mkv")
        path.write_bytes(FIXTURE_MEDIA)
        media[path.name] = sha(path)
    review_path = directory / "review.json"
    write_json(review_path, {
        "format": "c111662-4033-original-review-v1",
        "source_kind": "synthetic_fixture_review",
        "reviewer_id": "cpu-fixture-only",
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "raw_sha256": sha(directory / "native-raw-actors.jsonl"),
        "video_frames_sha256": sha(directory / "video_frames.jsonl"),
        "map_sha256": sha(directory / "native-map-readback.json"),
        "capture_report_sha256": sha(directory / "native-capture-report.json"),
        "media_sha256": media,
        "vehicle_and_centerline_visible": False,
        "turn_path_visible": False,
        "intersection_extent_reviewed": False,
        "district_designation_reviewed": False,
        "divided_highway_exception_reviewed": False})
    return review_path


def refresh_review(directory, review_path):
    review = json.loads(review_path.read_text())
    review["raw_sha256"] = sha(directory / "native-raw-actors.jsonl")
    review["video_frames_sha256"] = sha(directory / "video_frames.jsonl")
    review["map_sha256"] = sha(directory / "native-map-readback.json")
    review["capture_report_sha256"] = sha(directory / "native-capture-report.json")
    review["media_sha256"] = {camera + ".mkv": sha(directory / (camera + ".mkv"))
                              for camera in CAMERAS}
    write_json(review_path, review)


def change_json(path, change):
    data = json.loads(path.read_text())
    change(data)
    write_json(path, data)


def change_line(path, index, change):
    data = [json.loads(line) for line in path.read_text().splitlines()]
    change(data[index])
    write_rows(path, data)


def prove(bundle):
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        review = fixture(bundle, directory)
        result = process(bundle, directory, review, synthetic_fixture=True)
        assert result["frames_joined"] == 800
        assert result["original_native_observed"] is False
        assert result["delivery_ready"] is False
        assert result["crossing_in_authored_intersection_zone"] == (bundle.parent.name == "contrast")
        negatives = []
        def rejected(name, change, *, refresh=False):
            before = {path: path.read_bytes() for path in directory.iterdir() if path.is_file()}
            try:
                change()
                if refresh:
                    refresh_review(directory, review)
                try:
                    process(bundle, directory, review, synthetic_fixture=True)
                except ValueError:
                    negatives.append(name)
                else:
                    raise AssertionError("Mutation accepted: " + name)
            finally:
                for path, content in before.items():
                    path.write_bytes(content)
        rejected("changed_actor_id", lambda: change_line(
            directory / "native-raw-actors.jsonl", 5,
            lambda row: row["ego"].update(actor_id=98)), refresh=True)
        rejected("changed_video_frame", lambda: change_line(
            directory / "video_frames.jsonl", 5,
            lambda row: row.update(video_frame=6)), refresh=True)
        rejected("changed_actor_body", lambda: change_line(
            directory / "native-raw-actors.jsonl", 5,
            lambda row: row["ego"]["body_native_xyz_m"][0].__setitem__(0, 100)), refresh=True)
        rejected("changed_generated_lane", lambda: change_json(
            directory / "native-map-readback.json",
            lambda row: row["lane_readback"]["junction_eastbound_outer"].update(road_id=403)),
            refresh=True)
        rejected("changed_media", lambda: (directory / "overview.mkv").write_bytes(b"altered"),
                 refresh=True)
        rejected("changed_review_digest", lambda: change_json(
            review, lambda row: row.update(raw_sha256="0" * 64)))
        try:
            process(bundle, directory, review)
        except ValueError:
            negatives.append("fixture_rejected_as_original")
        else:
            raise AssertionError("Synthetic marker accepted as original FFV1")
        return {"case_id": result["case_id"], "candidate_id": result["candidate_id"],
                "positive_count": 1, "negative_count": len(negatives),
                "negative_names": negatives,
                "observed_crossing_x_m": result["observed_crossing_x_m"],
                "observed_heading_change_deg": result["observed_heading_change_deg"],
                "crossing_in_authored_intersection_zone":
                    result["crossing_in_authored_intersection_zone"],
                "synthetic_fixture_only": True,
                "original_native_observed": False, "delivery_ready": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.bundle)))
