"""Independent exact-case source, lifecycle, media and physical delivery audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = "testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator"
SOURCES = ("night-parking-trace.jsonl", "trace.jsonl", "video_frames.jsonl",
           "context.json", "classification.json", "activity.json",
           "night-parking-sources.json", "acquisition.json", "road.xodr")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    attempt, processing_path, decode_receipt = map(Path, (attempt, processing_path, decode_receipt))
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong nighttime parking assignment")
    config = read(attempt / "config.json")
    if (config.get("selected_case_id") != case_id or config.get("law_id") != "LVMC-11-52-300"
            or config.get("cell_id") != "C229435"
            or config.get("actor") != "horse_drawn_vehicle_operator"):
        raise ValueError("selected nighttime parking identity differs")
    seal = read(attempt / "capture-seal.json")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Native capture lifecycle incomplete")
    if not set(SOURCES) <= set(seal.get("sources", {})):
        raise ValueError("Native seal omits original nighttime parking source")
    for name, checksum in seal["sources"].items():
        if not (attempt / name).is_file() or sha(attempt / name) != checksum:
            raise ValueError("sealed original missing or changed: " + name)
    native_exit = read(attempt / "native-exit.json")
    if native_exit.get("event") != "native_exit" or native_exit.get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
        raise ValueError("Native exit does not bind sealed capture")
    owner = read(attempt / "owner-release.json")
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True
            or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
        raise ValueError("owner release missing or stale")
    provenance = read(attempt / "acquisition-provenance.json")
    if not protocol_fixture and (provenance.get("provenance_kind") != "native" or
                                 provenance.get("diagnostic_fixture") is not False):
        raise ValueError("synthetic diagnostic is not a Native delivery")
    acquisition = read(attempt / "acquisition.json")
    for name in SOURCES[:7]:
        source = acquisition.get(name, {})
        if source.get("sha256") != sha(attempt / name) or (not protocol_fixture and source.get("kind") != "original_native"):
            raise ValueError("original nighttime source absent or stale: " + name)
    source_manifest = read(attempt / "night-parking-sources.json")
    if source_manifest.get("format") != "night-parking-original-sources-v1":
        raise ValueError("wrong original source manifest")
    for source in source_manifest["sources"].values():
        if sha(attempt / source["path"]) != source["sha256"]:
            raise ValueError("original nighttime source manifest stale: " + source["path"])
    detailed, trace, mapping = (rows(attempt / name) for name in
                                ("night-parking-trace.jsonl", "trace.jsonl", "video_frames.jsonl"))
    if not detailed or len(detailed) != len(trace) or len(trace) != len(mapping):
        raise ValueError("original nighttime frame streams incomplete")
    for index, (parked, motion, video) in enumerate(zip(detailed, trace, mapping)):
        if (video.get("video_frame") != index or parked.get("frame") != video.get("carla_frame")
                or motion.get("frame") != video.get("carla_frame")
                or abs(motion.get("time_s", -1) - video.get("time_s", -2)) > 1e-6
                or not parked.get("subject", {}).get("body_vertices_xy_m")
                or not parked.get("other_vehicle", {}).get("body_vertices_xy_m")):
            raise ValueError("original parked/other body frame-time join differs")
    activity = read(attempt / "activity.json")
    parked_frames = [row["frame"] for row in detailed if row["subject"].get("parked") and row["subject"].get("on_street")]
    if (len(parked_frames) < 2 or parked_frames != list(range(parked_frames[0], parked_frames[-1] + 1))
            or activity.get("start_frame") != parked_frames[0]
            or activity.get("end_frame") != parked_frames[-1]):
        raise ValueError("original parking episode/event join incomplete")
    processing = read(processing_path)
    if (processing.get("format") != "worker-saved-processing" or processing.get("passed") is not True
            or processing.get("recorded_only") is not True or processing.get("case_id") != case_id):
        raise ValueError("saved-only processing receipt absent or failed")
    if not protocol_fixture:
        for name in SOURCES:
            if processing.get("original_source_hashes", {}).get(name) != sha(attempt / name):
                raise ValueError("saved processing source binding stale: " + name)
    result_path = Path(processing.get("result", ""))
    if not result_path.is_file() or processing.get("result_sha256") != sha(result_path):
        raise ValueError("saved result missing or stale")
    result = read(result_path)
    if result.get("case_id") != case_id or not result.get("physical_checks") or result.get("physical_acceptance_claimed"):
        raise ValueError("saved physical checks absent or acceptance overclaimed")
    if not protocol_fixture and (not all(result.get(key) is True for key in
                                  ("setup_confirmed", "behavior_attempted", "maneuver_completed"))
                                 or result["physical_checks"]["maneuver"].get("status") != "met"):
        raise ValueError("physical completion not established for exact parking case")
    video = Path(processing["analysis_directory"]) / "raw.mkv"
    if not video.is_file():
        raise ValueError("saved primary video missing")
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping), mapping_sha256=sha(attempt / "video_frames.jsonl"))
    if not protocol_fixture:
        review = read(attempt / "pixel-review.json")
        if (not review.get("reviewer") or review["reviewer"] == "CPU fixture"
                or review.get("video_sha256") != sha(video)
                or review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl")
                or not all(review.get(key) is True for key in
                           ("both_vehicle_bodies_visible", "responsible_person_visible",
                            "street_context_visible", "full_interval_legible"))):
            raise ValueError("independent actual-pixel review missing or stale")
    return {"format": "worker-delivery-audit", "passed": not protocol_fixture,
            "protocol_fixture_checked": protocol_fixture, "case_id": case_id,
            "assignment_id": ASSIGNMENT, "frame_count": len(mapping),
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "result_sha256": sha(result_path), "video_sha256": sha(video),
            "physical_acceptance_claimed": False, "legal_verdict": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--protocol-fixture", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt,
                           args.case, protocol_fixture=args.protocol_fixture), indent=2))


if __name__ == "__main__":
    main()
