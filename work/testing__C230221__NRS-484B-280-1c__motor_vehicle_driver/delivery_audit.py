"""Independent source and saved-media audit for an crosswalk pedestrian case."""
import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure


ORIGINAL = ("encounter-history.jsonl", "crosswalk-site.json", "map.xodr",
            "trace.jsonl", "video_frames.jsonl", "acquisition.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, processing, decode_receipt, case_id, media_verify=None):
    attempt, processing, decode_receipt = map(Path, (attempt, processing, decode_receipt))
    seal = read(attempt / "capture-seal.json")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Native capture lifecycle incomplete")
    if not set(ORIGINAL) <= set(seal.get("sources", {})):
        raise ValueError("Native seal omits original crosswalk pedestrian source")
    for name, digest in seal["sources"].items():
        if not (attempt / name).is_file() or sha(attempt / name) != digest:
            raise ValueError("sealed original missing or changed: " + name)
    native_exit = read(attempt / "native-exit.json")
    if native_exit.get("event") != "native_exit" or native_exit.get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
        raise ValueError("Native exit does not bind capture seal")
    owner = read(attempt / "owner-release.json")
    if owner.get("event") != "owner_released" or owner.get("operator_attested") is not True or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json"):
        raise ValueError("Native owner release absent or stale")
    result = read(attempt / "result.json")
    if result.get("case_id") != case_id or not all(result.get(key) is True for key in
            ("setup_confirmed", "behavior_attempted", "maneuver_completed")):
        raise ValueError("physical completion not confirmed for exact case")
    acquisition = read(attempt / "acquisition.json")
    for name in ORIGINAL[:3]:
        info = acquisition.get(name, {})
        if info.get("kind") != "original_native" or info.get("sha256") != sha(attempt / name):
            raise ValueError("original road or pedestrian source absent: " + name)
    history, trace, mapping = (rows(attempt / name) for name in
                               ("encounter-history.jsonl", "trace.jsonl", "video_frames.jsonl"))
    if not history or not len(history) == len(trace) == len(mapping):
        raise ValueError("original encounter/frame streams incomplete")
    for index, (encounter, motion, frame) in enumerate(zip(history, trace, mapping)):
        ident = frame.get("carla_frame"), frame.get("time_s")
        if frame.get("video_frame") != index or any(
            (row.get("frame"), row.get("time_s")) != ident for row in (encounter, motion)
        ):
            raise ValueError("original encounter/frame identity join changed")
    value, _, _, site = measure(attempt)
    if value["first_observation"] is None:
        raise ValueError("original scripted-driver input event absent")
    if value["first_brake"] is None:
        raise ValueError("original motorist brake response absent")
    processed = read(processing)
    if (processed.get("format") != "worker-saved-processing" or
            processed.get("passed") is not True or processed.get("recorded_only") is not True):
        raise ValueError("saved-only processing receipt absent or failed")
    saved_result = Path(processed.get("result", ""))
    if not saved_result.is_file() or processed.get("result_sha256") != sha(saved_result) or read(saved_result).get("case_id") != case_id:
        raise ValueError("saved result missing, stale or wrong case")
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    video = Path(processed.get("analysis_directory", "")) / "raw.mkv"
    if not video.is_file():
        raise ValueError("saved primary video absent")
    media_verify(video, decode_receipt, len(mapping), mapping_sha256=sha(attempt / "video_frames.jsonl"))
    config = read(attempt / "config.json")
    scene = read(attempt / "scene.json")
    expected_kind = case_id.rsplit("__", 1)[-1].removesuffix("_crosswalk")
    if (expected_kind not in ("marked", "unmarked") or
            scene.get("crosswalk_kind") != expected_kind or
            config.get("case", {}).get("crosswalk_kind") != expected_kind or
            scene.get("response_policy") != "fixed_brake" or
            config.get("case", {}).get("response_policy") != "fixed_brake"):
        raise ValueError("saved crossing kind or fixed controller differs from exact case")
    fixed_scene = {key: scene[key] for key in
                   ("ego_start_xy_m", "ego_end_xy_m", "pedestrian_start_xy_m",
                    "pedestrian_end_xy_m", "instrumented_observation_distance_m",
                    "pedestrian_target_speed_mps", "duration_s", "rate_hz")}
    return {"format": "worker-delivery-audit", "passed": True, "case_id": case_id,
            "law_id": config["law_id"], "cell_id": config["cell_id"], "actor_id": config["actor"],
            "map_sha256": sha(attempt / "map.xodr"),
            "crosswalk_site_sha256": hashlib.sha256(json.dumps(site, sort_keys=True).encode()).hexdigest(),
            "crossing_geometry_sha256": hashlib.sha256(json.dumps({k: site[k] for k in
                ("intersecting_road_ids", "crossing_polygon_xy_m", "near_curb_polygon_xy_m",
                 "far_curb_polygon_xy_m", "pedestrian_route_xy_m", "ego_route_xy_m")},
                sort_keys=True).encode()).hexdigest(),
            "fixed_scene_sha256": hashlib.sha256(json.dumps(fixed_scene, sort_keys=True).encode()).hexdigest(),
            "participant_classes": ["motor_vehicle", "pedestrian"],
            "camera_contract_sha256": hashlib.sha256(json.dumps(config["cameras"], sort_keys=True).encode()).hexdigest(),
            "duration_s": config["duration_s"], "response_policy": "fixed_brake", "crosswalk_kind": expected_kind,
            "measurement": value, "native_result_sha256": sha(attempt / "result.json"),
            "frame_count": len(mapping), "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "video_sha256": sha(video), "source_decode_receipt_sha256": sha(decode_receipt),
            "human_observation_claimed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt, args.case), indent=2))


if __name__ == "__main__":
    main()
