"""Synthetic source-shape proof for original capture processing; no CARLA claim."""
import json
import math
from pathlib import Path
import tempfile

from build import HERE, FRAMES, RATE, put
from process_original import CAMERAS, LANES, process, sha
from saved import body, other_body


def write_lines(path, rows):
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def fixture(bundle, directory):
    bundle, directory = Path(bundle), Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    raw, video = [], []
    for i, row in enumerate(requests):
        actors = {}
        for key, axis, blueprint, points in (("ego", 0, cfg["ego_blueprint"], body),
                                             ("other", 1, cfg["other_blueprint"], other_body)):
            center = row["requested_" + key + "_xyz_m"]
            next_center = requests[min(i+1, FRAMES-1)]["requested_" + key + "_xyz_m"]
            velocity = [(next_center[j]-center[j])*RATE for j in range(3)]
            actors[key] = {"actor_id": 10 if key == "ego" else 11, "blueprint": blueprint,
                           "center_native_xyz_m": center,
                           "yaw_deg": 0 if key == "ego" else 90,
                           "velocity_native_xyz_mps": velocity,
                           "speed_mps": math.sqrt(sum(v*v for v in velocity)),
                           "body_native_xyz_m": points(center)}
        raw.append({"frame": i, "native_frame": 100+i, "time_s": (i+1)/RATE,
                    "source_kind": "synthetic_fixture", "request_frame": i,
                    "ego": actors["ego"], "other": actors["other"],
                    "ego_road_id": 250 if actors["ego"]["center_native_xyz_m"][0] < -20 else 251 if actors["ego"]["center_native_xyz_m"][0] < 20 else 252,
                    "other_road_id": 253 if actors["other"]["center_native_xyz_m"][1] < -20 else 254 if actors["other"]["center_native_xyz_m"][1] < 20 else 255,
                    "requested_ego_phase": row["requested_ego_phase"],
                    "authored_official_device_count": 0, "legal_verdict": None})
        video.append({"video_frame": i, "native_frame": 100+i, "time_s": (i+1)/RATE})
    write_lines(directory / "native-raw-actors.jsonl", raw)
    write_lines(directory / "video_frames.jsonl", video)
    put(directory / "native-map-readback.json", {
        "source_kind": "synthetic_fixture", "road_sha256": sha(bundle / "crossroads.xodr"),
        "native_map_sha256": "0"*64, "junction_id": 1, "authored_signal_count": 0,
        "lane_readback": {name: {"road_id": road_id, "lane_id": -1,
                                 "native_xyz_m": [0, 0, 0], "lane_type": "Driving"}
                          for name, road_id in LANES.items()},
        "ego_actor_id": 10, "other_actor_id": 11, "legal_verdict": None})
    put(directory / "native-capture-report.json", {
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "config_sha256": sha(bundle / "config.json"), "requested_frames": FRAMES,
        "observed_frames": FRAMES, "restoration": {"restored": True}, "error": None,
        "accepted": False, "delivery_ready": False, "legal_verdict": None})
    for name in CAMERAS:
        (directory / (name + ".mkv")).write_bytes(b"C111294 SYNTHETIC FIXTURE; NOT VIDEO\n")
    review_path = directory / "fixture-review.json"
    refresh_review(bundle, directory, review_path)
    return review_path


def refresh_review(bundle, directory, review_path):
    cfg = json.loads((bundle / "config.json").read_text())
    put(review_path, {"format": "c111294-2502-original-review-v1",
        "source_kind": "synthetic_fixture_review", "reviewer_id": "synthetic-source-shape-test",
        "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
        "raw_sha256": sha(directory / "native-raw-actors.jsonl"),
        "video_frames_sha256": sha(directory / "video_frames.jsonl"),
        "map_sha256": sha(directory / "native-map-readback.json"),
        "capture_report_sha256": sha(directory / "native-capture-report.json"),
        "media_sha256": {name + ".mkv": sha(directory / (name + ".mkv")) for name in CAMERAS},
        "right_side_other_visible": False, "official_device_governance_reviewed": False,
        "yield_sequence_visible": False, "opposite_direction_left_turn_exclusion_reviewed": False,
        "subsection4_reviewed": False})


def prove():
    bundle = HERE / "drafts" / "controlled_1" / "primary"
    negatives = []
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        review = fixture(bundle, directory)
        saved = process(bundle, directory, review, synthetic_fixture=True)
        if saved["frames_joined"] != FRAMES or saved["original_native_observed"]:
            raise ValueError("Synthetic fixture was misclassified")
        def rejected(name, mutate, *, refresh=False):
            files = {p: p.read_bytes() for p in directory.iterdir() if p.is_file()}
            try:
                mutate()
                if refresh: refresh_review(bundle, directory, review)
                try: process(bundle, directory, review, synthetic_fixture=True)
                except ValueError: negatives.append(name)
                else: raise AssertionError("Mutation accepted: " + name)
            finally:
                for path, content in files.items(): path.write_bytes(content)
        def change_json(name, change):
            path = directory / name
            data = json.loads(path.read_text()); change(data); put(path, data)
        def change_line(name, index, change):
            path = directory / name
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            change(rows[index]); write_lines(path, rows)
        rejected("changed_actor_id", lambda: change_line("native-raw-actors.jsonl", 5,
                 lambda row: row["ego"].update(actor_id=99)), refresh=True)
        rejected("changed_video_frame", lambda: change_line("video_frames.jsonl", 5,
                 lambda row: row.update(video_frame=6)), refresh=True)
        rejected("changed_actor_body", lambda: change_line("native-raw-actors.jsonl", 5,
                 lambda row: row["ego"]["body_native_xyz_m"][0].__setitem__(0, 100)), refresh=True)
        rejected("changed_generated_lane", lambda: change_json("native-map-readback.json",
                 lambda row: row["lane_readback"]["other_connector"].update(road_id=250)), refresh=True)
        rejected("changed_media", lambda: (directory / "overview.mkv").write_bytes(b"altered"), refresh=True)
        rejected("changed_review_digest", lambda: change_json("fixture-review.json",
                 lambda row: row.update(raw_sha256="0"*64)))
        try: process(bundle, directory, review)
        except ValueError: negatives.append("fixture_rejected_as_original")
        else: raise AssertionError("Fixture accepted as original")
    proof = {"format": "c111294-2502-original-shape-proof-v1", "positive_count": 1,
             "negative_count": len(negatives), "negatives": negatives,
             "synthetic_fixture_only": True, "original_native_observed": False,
             "delivery_ready": False}
    put(HERE / "original-shape-proof.json", proof)
    return proof


if __name__ == "__main__":
    print(json.dumps(prove()))
