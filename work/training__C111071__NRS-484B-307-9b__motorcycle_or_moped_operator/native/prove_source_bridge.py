"""Controlled source-bridge fixture; no original CARLA or physical claim."""
import json
from pathlib import Path
import tempfile

from source_bridge import convert, sha


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".runtime-work"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    attempt = root / "attempt"
    attempt.mkdir()
    map_sha = "synthetic-road-hash"
    survey = {"map_sha256": map_sha,
              "road_reference": {"map_sha256": map_sha,
                                 "approach_road_id": 1, "lane_id": -1,
                                 "stop_marking_y_m": -14,
                                 "nearest_crosswalk_y_m": -10,
                                 "junction_entry_y_m": -7,
                                 "detector_center_x_m": 1.75,
                                 "detector_y_m": -16,
                                 "detector_half_width_m": .75,
                                 "detector_half_length_m": 1},
              "signal_actors": [{"role": role, "id": actor_id}
                                for role, actor_id in (("red", 11), ("arrow", 12),
                                                       ("cross", 13))]}
    write(attempt / "map-import-survey.json", survey)
    raw, frames = [], []
    lawful = []
    for index in range(600):
        native_frame, time = 100 + index, index / 20
        phase = ("green", "yellow", "red")[(index % 120) // 40]
        front = -20 if index < 15 else -14.5 if index < 250 else -6
        body = [[x, y, z] for x in (1, 2) for y in (front - 2, front)
                for z in (0, 1)]
        raw.append({"native_frame": native_frame, "time_s": time,
                    "source_kind": "native_observation",
                    "road_relation_from_original_body": {
                        "source_map_sha256": map_sha,
                        "entered_intersection_by_body": index >= 250,
                        "detector_footprint_intersects_ego_body": 15 <= index < 250,
                        "front_to_stop_marking_m": -14 - front,
                        "front_to_crosswalk_m": -10 - front},
                    "signal_actor_ids": {"red": 11, "arrow": 12, "cross": 13},
                    "signal_readback": {"red": "red", "arrow": "green", "cross": phase},
                    "controller_cycle_count_from_readback": index // 120,
                    "speed_mps": 3 if index < 15 or index >= 250 else 0,
                    "body_vertices_m": body})
        frames.append({"native_frame": native_frame, "video_frame": index,
                       "time_s": time})
        lawful.append({"pedestrians_in_crosswalk": False,
                       "lawful_traffic_conflict": False,
                       "source_refs": ["synthetic-original-frame-" + str(native_frame)]})
    (attempt / "native_raw_readback.jsonl").write_text("".join(
        json.dumps(row) + "\n" for row in raw))
    (attempt / "video_frames.jsonl").write_text("".join(
        json.dumps(row) + "\n" for row in frames))
    source_hashes = {name: sha(attempt / name) for name in
                     ("native_raw_readback.jsonl", "video_frames.jsonl",
                      "map-import-survey.json")}
    review = {"review_kind": "original_source_review", "reviewer": "synthetic-cpu-fixture",
              "source_sha256": source_hashes,
              "governing_face": "circular_red_green_left_arrow",
              "governing_face_source_refs": ["synthetic-pixel-source"],
              "other_device_prohibition_survey": False,
              "other_device_source_refs": ["synthetic-device-source"],
              "detector_request_observed": True,
              "detector_request_source_refs": ["synthetic-detector-source"],
              "detector_serviced_before_entry": False,
              "participant_lawful_status_source_refs": ["synthetic-participant-source"],
              "lawful_conflict_by_frame": lawful}
    review_path = root / "review.json"
    write(review_path, review)
    return attempt, review_path, review


def main():
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c111071-bridge-", dir=SCRATCH) as tmp:
        root = Path(tmp)
        attempt, review_path, review = fixture(root)
        result = convert(attempt, review_path)
        from saved_measurement import analyze
        measured = analyze(attempt)
        if not measured["case_observation"]["two_cycles_before_entry"]:
            raise AssertionError("Two source-derived cycles not measured")
        if measured["case_observation"]["entry_frame"] != 250:
            raise AssertionError("Source-derived entry frame differs")
        rejections = []
        for label, mutation in (
                ("stale_source", lambda r: r["source_sha256"].update(
                    {"native_raw_readback.jsonl": "0" * 64})),
                ("missing_face_review", lambda r: r.pop("governing_face_source_refs")),
                ("missing_device_review", lambda r: r.pop("other_device_source_refs")),
                ("missing_detector_review", lambda r: r.pop("detector_request_source_refs")),
                ("missing_lawful_frame", lambda r: r["lawful_conflict_by_frame"].pop())):
            bad_attempt, bad_review_path, bad_review = fixture(root / label)
            mutation(bad_review)
            write(bad_review_path, bad_review)
            try:
                convert(bad_attempt, bad_review_path)
            except ValueError:
                rejections.append(label)
            else:
                raise AssertionError("Rejected source mutation accepted: " + label)
        bad_attempt, bad_review_path, bad_review = fixture(root / "forged_entry_relation")
        raw_path = bad_attempt / "native_raw_readback.jsonl"
        changed = [json.loads(line) for line in raw_path.read_text().splitlines()]
        changed[20]["road_relation_from_original_body"]["entered_intersection_by_body"] = True
        raw_path.write_text("".join(json.dumps(row) + "\n" for row in changed))
        bad_review["source_sha256"]["native_raw_readback.jsonl"] = sha(raw_path)
        write(bad_review_path, bad_review)
        try:
            convert(bad_attempt, bad_review_path)
        except ValueError as error:
            if "retained vertices and map" not in str(error):
                raise
            rejections.append("forged_entry_relation")
        else:
            raise AssertionError("Forged source entry relation accepted")
        receipt = {"format": "c111071-source-bridge-cpu-proof-v1",
                   "passed": True, "synthetic_source_only": True,
                   "original_native_observed": False,
                   "physical_detector_causation_verified": False,
                   "bridge_sha256": sha(HERE / "source_bridge.py"),
                   "frame_count": result["frames"],
                   "measured_entry_frame": measured["case_observation"]["entry_frame"],
                   "negative_rejections": rejections}
        path = HERE / "source-bridge-proof.json"
        write(path, receipt)
        print(json.dumps({"passed": True, "negative_rejections": len(rejections),
                          "receipt_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
