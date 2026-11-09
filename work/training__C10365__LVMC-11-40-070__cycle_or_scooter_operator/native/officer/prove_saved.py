"""Synthetic saved-pipeline positives and material negatives; no original evidence."""
import json
from pathlib import Path
import tempfile

from build import HERE, CASES, POLICIES, build
from saved import process


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def fixture(bundle, target):
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    raw, video = [], []
    officer_x, officer_y = cfg["officer_position_xy_m"]
    for i, request in enumerate(requests):
        x = request["requested_rider_x_m"]
        speed = request["requested_speed_mps"]
        raw.append({
            "frame": i, "native_frame": i + 1000, "time_s": (i + 1) / 20,
            "source_kind": "synthetic_fixture", "officer_cue_requested": cfg["officer_cue_requested"],
            "requested_rider_x_m": request["requested_rider_x_m"],
            "requested_speed_mps": request["requested_speed_mps"],
            "observed_road_id": 365, "observed_lane_id": -1,
            "rider": {"actor_id": 17, "blueprint": cfg["rider_blueprint"],
                      "center_native_xyz_m": [x, -1.75, 1.0],
                      "velocity_native_xyz_mps": [speed, 0, 0],
                      "speed_mps": speed,
                      "body_native_xyz_m": [[x + dx, -1.75 + dy, 1.0]
                                             for dx in (-1, 1) for dy in (-.5, .5)
                                             for _ in (0, 1)]},
            "officer_actor": {
                "actor_id": 23, "blueprint": "walker.pedestrian.0001",
                "center_native_xyz_m": [officer_x, officer_y, 1.0],
                "velocity_native_xyz_mps": [0, 0, 0], "speed_mps": 0,
                "body_native_xyz_m": [[officer_x + dx, officer_y + dy, 1.0]
                                      for dx in (-.3, .3) for dy in (-.3, .3)
                                      for _ in (0, 1)]},
        })
        video.append({"video_frame": i, "native_frame": i + 1000, "time_s": (i + 1) / 20})
    review = {
        "source_kind": "synthetic_fixture", "case_id": cfg["case_id"],
        "candidate_id": cfg["candidate_id"], "reviewed_frames": [100, 150],
        "device_id": "3651", "device_applicable": True, "rider_class": "bicycle",
        "officer_actor_id": 23,
        "officer_direction": "none_contrary" if cfg["case_id"].endswith("probe_a") else "proceed",
        "direction_start_frame": None if cfg["case_id"].endswith("probe_a") else 100,
        "direction_end_frame": None if cfg["case_id"].endswith("probe_a") else 150,
        "officer_authority_reviewed": cfg["case_id"].endswith("probe_b"),
        "direction_visible": cfg["case_id"].endswith("probe_b"),
        "officer_cue_visibility": .97,
        "reviewer": "synthetic",
    }
    paths = [target / "raw.jsonl", target / "video.jsonl", target / "review.json"]
    write_rows(paths[0], raw)
    write_rows(paths[1], video)
    paths[2].write_text(json.dumps(review))
    return paths


def prove():
    build()
    positives, negatives = [], []
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        for suffix in CASES:
            for candidate in POLICIES:
                bundle = HERE / "drafts" / suffix / candidate
                raw, video, review = fixture(bundle, target)
                positives.append(process(bundle, raw, video, review, synthetic=True))
                base_raw = raw.read_text()
                base_video = video.read_text()
                base_review = review.read_text()
                mutations = (
                    ("frame_join", video, base_video.replace('"native_frame": 1000', '"native_frame": 999', 1)),
                    ("actor_class", raw, base_raw.replace("vehicle.bh.crossbike", "vehicle.tesla.model3", 1)),
                    ("officer_cue", raw, base_raw.replace(CASES[suffix], "unrelated", 1)),
                    ("device_applicability", review, base_review.replace('"device_applicable": true', '"device_applicable": false')),
                    ("officer_identity", review, base_review.replace('"officer_actor_id": 23', '"officer_actor_id": 99')),
                    ("direction", review, base_review.replace(
                        '"officer_direction": "none_contrary"' if suffix == "probe_a" else
                        '"officer_direction": "proceed"', '"officer_direction": "unreviewed"')),
                )
                for name, path, bad in mutations:
                    path.write_text(bad)
                    try:
                        process(bundle, raw, video, review, synthetic=True)
                    except (ValueError, KeyError) as exc:
                        negatives.append({"case": suffix, "candidate": candidate,
                                          "mutation": name, "rejected": str(exc)})
                    else:
                        raise AssertionError(f"{suffix}/{candidate}/{name} accepted")
                    path.write_text({raw: base_raw, video: base_video, review: base_review}[path])
                raw.write_text(base_raw.replace('"source_kind": "synthetic_fixture"',
                                                '"source_kind": "original_native"'))
                review.write_text(base_review.replace('"source_kind": "synthetic_fixture"',
                                                      '"source_kind": "original_native_review"'))
                try:
                    process(bundle, raw, video, review, synthetic=False)
                except ValueError as exc:
                    if "Original FFV1 camera missing" not in str(exc):
                        raise
                    negatives.append({"case": suffix, "candidate": candidate,
                                      "mutation": "missing_original_media", "rejected": str(exc)})
                else:
                    raise AssertionError(f"{suffix}/{candidate}/missing_original_media accepted")
                review.write_text(base_review)
                structured = (
                    ("rider_velocity", lambda rows: rows[0]["rider"].update(
                        velocity_native_xyz_mps=[0, 0, 0])),
                    ("officer_body", lambda rows: rows[0]["officer_actor"].update(
                        body_native_xyz_m=[])),
                    ("rider_displacement", lambda rows: rows[1]["rider"][
                        "center_native_xyz_m"].__setitem__(0, 99.0)),
                    ("source_time", lambda rows: rows[0].update(time_s=.4)),
                    ("requested_source", lambda rows: rows[0].update(requested_speed_mps=99)),
                )
                for name, mutate in structured:
                    rows = [json.loads(line) for line in base_raw.splitlines()]
                    mutate(rows)
                    write_rows(raw, rows)
                    try:
                        process(bundle, raw, video, review, synthetic=True)
                    except (ValueError, KeyError) as exc:
                        negatives.append({"case": suffix, "candidate": candidate,
                                          "mutation": name, "rejected": str(exc)})
                    else:
                        raise AssertionError(f"{suffix}/{candidate}/{name} accepted")
    result = {"format": "c10365-synthetic-saved-proof-v1",
              "positive_count": len(positives), "negative_count": len(negatives),
              "positives": positives, "negatives": negatives,
              "physical_original_observed": False, "delivery_ready": False}
    (HERE / "saved-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = prove()
    print(json.dumps({"positive_count": result["positive_count"],
                      "negative_count": result["negative_count"]}))
