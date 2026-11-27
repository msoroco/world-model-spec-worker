"""Independent original signed roadway delivery audit; fixtures only test the protocol."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from signed_road import AID, BY_SUFFIX, SOURCE_ROLES, measure_original, original_site

SOURCES = ("signed-road-history.jsonl", "signed-road-site.json", "trace.jsonl",
           "video_frames.jsonl", "road.xodr", "carla_recorder.log",
           "overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(attempt, processing_path, decode_receipt, case_id, *,
          protocol_fixture=False, media_verify=None):
    root = Path(attempt).resolve()
    suffix = case_id.removeprefix(AID + "__")
    case = BY_SUFFIX.get(suffix)
    require(case_id.startswith(AID + "__") and case is not None,
            "wrong signed roadway case identity")
    seal = read(root / "capture-seal.json")
    require(seal.get("events") == ["capture_finished", "encoders_closed",
                                   "restoration_verified"],
            "Native capture lifecycle incomplete")
    expected = SOURCES if not protocol_fixture else SOURCES[:5] + SOURCES[6:]
    require(set(expected) <= set(seal.get("sources", {})),
            "Native seal omits original signed roadway source")
    for name, digest in seal["sources"].items():
        require((root / name).is_file() and sha(root / name) == digest,
                "sealed original missing or changed: " + name)
    native_exit = read(root / "native-exit.json")
    require(native_exit.get("event") == "native_exit" and
            native_exit.get("capture_seal_sha256") == sha(root / "capture-seal.json"),
            "Native exit does not bind sealed capture")
    owner = read(root / "owner-release.json")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(root / "native-exit.json"),
            "owner release missing or stale")
    provenance = read(root / "acquisition-provenance.json")
    if not protocol_fixture:
        require(provenance.get("provenance_kind") == "native" and
                provenance.get("diagnostic_fixture") is False,
                "synthetic diagnostic is not original Native delivery")
    config = read(root / "config.json")
    require(config.get("selected_case_id") == case_id and
            config.get("law_id") == "LVMC-11-40-180-B" and
            config.get("cell_id") == "C412927" and
            config.get("actor") == "cycle_or_scooter_operator",
            "original signed roadway config identity differs")
    history = rows(root / "signed-road-history.jsonl")
    trace = rows(root / "trace.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    require(history and len(history) == len(trace) == len(mapping) == seal.get("frames"),
            "original signed roadway frame streams incomplete")
    for index, (device, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get("carla_frame"), video.get("time_s"))
        require(video.get("video_frame") == index and
                (device.get("original_frame"), device.get("time_s")) == identity and
                (motion.get("frame"), motion.get("time_s")) == identity,
                "original signed roadway frame/time join changed")
    site = read(root / "signed-road-site.json")
    if not protocol_fixture:
        acquisition = read(root / "acquisition.json")
        for name in SOURCES:
            require(acquisition.get(name, {}).get("kind") == "original_native" and
                    acquisition[name].get("sha256") == sha(root / name),
                    "original signed roadway source absent or stale: " + name)
        packet = root / "reviewed-signed-road-packet/site.json"
        require(read(packet) == site and original_site(packet, case) == site,
                "saved signed roadway site differs from reviewed original packet")
        require(len(history) == 900, "original signed roadway 900-frame measurement absent")
    measured = measure_original(history, site, case)
    processing = read(processing_path)
    require(processing.get("format") == "worker-saved-processing" and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("case_id") == case_id and
            processing.get("originals_preserved") is True,
            "saved-only signed roadway processing receipt absent or failed")
    if not protocol_fixture:
        for name in SOURCES:
            require(processing.get("original_source_hashes", {}).get(name) == sha(root / name),
                    "saved processing source binding stale: " + name)
    result_path = Path(processing.get("result", ""))
    require(result_path.is_file() and processing.get("result_sha256") == sha(result_path),
            "saved result missing or stale")
    result = read(result_path)
    require(result.get("case_id") == case_id and result.get("physical_checks"),
            "saved physical checks absent or wrong case")
    if not protocol_fixture:
        require(result.get("diagnostic_fixture") is False and
                all(result.get(key) is True for key in
                    ("setup_confirmed", "behavior_attempted", "maneuver_completed")),
                "physical completion not confirmed for original signed roadway travel")
    video = Path(processing.get("analysis_directory", "")) / "raw.mkv"
    require(video.is_file(), "saved primary signed roadway video missing")
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(root / "video_frames.jsonl"))
    if not protocol_fixture:
        pixel = read(root / "pixel-review.json")
        require(pixel.get("reviewer") and pixel.get("reviewer") != "CPU fixture" and
                pixel.get("video_sha256") == sha(video) and
                pixel.get("frame_map_sha256") == sha(root / "video_frames.jsonl") and
                all(pixel.get(key) is True for key in
                    ("device_body_visible", "operator_conduct_visible",
                     "roadway_boundary_visible", "sign_face_visible",
                     "sign_extent_visible")),
                "independent actual-pixel signed roadway review missing or stale")
    fixed_roles = ("municipal_jurisdiction", "native_map", "roadway_boundary",
                   "director_sign_order", "city_traffic_engineer_consultation",
                   "metropolitan_police_consultation",
                   "director_traffic_flow_determination")
    comparison = None if protocol_fixture else {
        "source_kind": "original_native_capture",
        "fixed_source_sha256": {role: site["sources"][role]["sha256"]
                                for role in fixed_roles},
        "camera_plan": config["cameras"], "duration_s": config["duration_s"],
        "requested_relation": suffix,
        "device_kind": site["device"]["kind"],
        "operator_conduct": site["operator_conduct"]["kind"],
        "surface": "roadway", "extent": case.extent, "movement": case.movement,
        "sign_state": case.sign_state,
        "sign_inventory_sha256": site["sign_inventory_source_sha256"],
        "station_survey": site["longitudinal_station_m"],
        "roadway_center_frames": measured["roadway_center_frames"],
        "frame_count": len(history)}
    return {"format": "worker-delivery-audit", "passed": not protocol_fixture,
            "protocol_fixture_checked": protocol_fixture,
            "case_id": case_id, "assignment_id": AID,
            "frame_count": len(mapping),
            "capture_seal_sha256": sha(root / "capture-seal.json"),
            "native_result_sha256": sha(result_path),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "video_sha256": sha(video),
            "source_decode_receipt_path": str(decode_receipt),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(__file__),
            "physical_acceptance_claimed": not protocol_fixture,
            "legal_judgment": None, "comparison_record": comparison}


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
