"""Independent original stop, follower, lifecycle, media and pixel audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from stop_model import ASSIGNMENT, BY_NAME, measure_original, reviewed_scene


SOURCES = ("stop-history.jsonl", "stop-scene.json", "trace.jsonl",
           "video_frames.jsonl", "road.xodr")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    root = Path(attempt).resolve()
    processing_path = Path(processing_path)
    decode_receipt = Path(decode_receipt)
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    require(case_id.startswith(ASSIGNMENT + "__") and suffix in BY_NAME,
            "wrong exact stop case identity")
    case = BY_NAME[suffix]
    seal = read(root / "capture-seal.json")
    require(seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"],
            "Native stop capture lifecycle incomplete")
    require(set(SOURCES) <= set(seal.get("sources", {})), "Native seal omits original stop source")
    for name, digest in seal["sources"].items():
        path = root / name
        require(path.is_file() and sha(path) == digest,
                "sealed original stop source missing or changed: " + name)
    native_exit = read(root / "native-exit.json")
    require(native_exit.get("event") == "native_exit" and
            native_exit.get("capture_seal_sha256") == sha(root / "capture-seal.json"),
            "Native exit does not bind sealed stop capture")
    owner = read(root / "owner-release.json")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(root / "native-exit.json"),
            "released original stop owner receipt missing or stale")
    provenance = read(root / "acquisition-provenance.json")
    if not protocol_fixture:
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False,
                "synthetic stop diagnostic is not original Native delivery")
    config = read(root / "config.json")
    require(config.get("selected_case_id") == case_id and
            config.get("law_id") == "NRS-484B-627-2" and
            config.get("cell_id") == "C150640" and
            config.get("actor") == "motor_vehicle_driver",
            "original stop config identity differs")
    history = rows(root / "stop-history.jsonl")
    trace = rows(root / "trace.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    require(history and len(history) == len(trace) == len(mapping) == seal.get("frames"),
            "original stop frame streams incomplete")
    for index, (participant, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get("carla_frame"), video.get("time_s"))
        require(video.get("video_frame") == index and
                (participant.get("original_frame"), participant.get("time_s")) == identity and
                (motion.get("frame"), motion.get("time_s")) == identity,
                "original stop participant/trace/camera join changed")
    if not protocol_fixture:
        acquisition = read(root / "acquisition.json")
        for name in (*SOURCES, "carla_recorder.log", *[camera + ".mkv" for camera in CAMERAS]):
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == sha(root / name),
                    "original stop source absent or stale: " + name)
        scene = reviewed_scene(root / "reviewed-stop-packet/scene.json", case_id)
        require(read(root / "stop-scene.json") == scene,
                "saved stop scene differs from reviewed original packet")
        measured = measure_original(history, scene, case)
        require(measured.get("frame_count") == 900,
                "original stop needs full 900-frame history")
    else:
        measured = measure_original(history, read(root / "stop-scene.json"), case)
    processing = read(processing_path)
    require(processing.get("format") == "worker-saved-processing" and
            processing.get("passed") is True and processing.get("recorded_only") is True and
            processing.get("case_id") == case_id,
            "saved-only stop processing receipt absent or failed")
    if not protocol_fixture:
        for name in SOURCES:
            require(processing.get("original_source_hashes", {}).get(name) == sha(root / name),
                    "saved stop processing source binding stale: " + name)
    result_path = Path(processing.get("result", ""))
    require(result_path.is_file() and processing.get("result_sha256") == sha(result_path),
            "saved stop result missing or stale")
    result = read(result_path)
    require(result.get("case_id") == case_id and result.get("physical_checks"),
            "saved stop physical checks absent or wrong case")
    if not protocol_fixture:
        require(all(result.get(key) is True for key in
                    ("setup_confirmed", "behavior_attempted", "maneuver_completed")),
                "physical stop/follower completion not confirmed")
    video = Path(processing.get("analysis_directory", "")) / "raw.mkv"
    require(video.is_file(), "saved synchronized primary stop video missing")
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(root / "video_frames.jsonl"))
    if not protocol_fixture:
        pixel = read(root / "pixel-review.json")
        required = ("one_way_road_visible", "ego_and_follower_visible",
                    "stop_footprint_visible", "roadway_edge_visible",
                    "traffic_response_visible")
        if case.stop_reason == "safety_conflict":
            required += ("conflict_actor_visible",)
        if case.stop_reason == "official_direction":
            required += ("official_direction_visible",)
        require(pixel.get("reviewer") not in (None, "CPU fixture") and
                pixel.get("video_sha256") == sha(video) and
                pixel.get("frame_map_sha256") == sha(root / "video_frames.jsonl") and
                all(pixel.get(key) is True for key in required),
                "independent actual-pixel stop review missing or stale")
    comparison_record = None
    if not protocol_fixture:
        fixed = ("map", "one_way_direction", "ego_driver", "ego_vehicle",
                 "follower_vehicle", "follower_driver", "jurisdiction")
        comparison_record = {
            "source_kind": "original_native_capture",
            "fixed_source_sha256": {name: scene["sources"][name]["sha256"] for name in fixed},
            "roadway_source_sha256": scene["sources"]["roadway_boundary"]["sha256"],
            "shoulder_source_sha256": scene["sources"]["shoulder_boundary"]["sha256"],
            "stop_purpose_source_sha256": scene["sources"]["stop_purpose"]["sha256"],
            "conflict_source_sha256": scene["sources"]["conflict_context"]["sha256"],
            "direction_source_sha256": scene["sources"]["official_direction"]["sha256"],
            "passing_space_source_sha256": scene["sources"]["passing_space"]["sha256"],
            "camera_plan": config["cameras"], "duration_s": config["duration_s"],
            "measurement": measured, "requested_surface": case.stop_surface,
            "requested_reason": case.stop_reason,
            "requested_follower_action": case.follower_action,
            "requested_complete_stop": case.complete_stop_requested}
    return {"format": "worker-delivery-audit", "passed": not protocol_fixture,
            "protocol_fixture_checked": protocol_fixture,
            "case_id": case_id, "assignment_id": ASSIGNMENT,
            "frame_count": len(mapping),
            "native_result_sha256": sha(result_path),
            "capture_seal_sha256": sha(root / "capture-seal.json"),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "video_sha256": sha(video),
            "source_decode_receipt_path": str(decode_receipt),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(__file__),
            "physical_acceptance_claimed": not protocol_fixture,
            "legal_verdict": None, "comparison_record": comparison_record}


def main():
    parser = argparse.ArgumentParser()
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--protocol-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt,
                           args.case, protocol_fixture=args.protocol_fixture), indent=2))


if __name__ == "__main__":
    main()
