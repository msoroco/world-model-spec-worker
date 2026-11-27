"""Independent source, lifecycle, measured-body and media audit for delivery."""

import argparse
import hashlib
import json
from pathlib import Path

from oneway_site import ASSIGNMENT, load_site


SOURCES = ("parking-history.jsonl", "parking-context.json", "trace.jsonl",
           "video_frames.jsonl", "acquisition.json", "road.xodr")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    attempt = Path(attempt)
    processing_path = Path(processing_path)
    decode_receipt = Path(decode_receipt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong one-way parking assignment")
    seal = read(attempt / "capture-seal.json")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Native capture lifecycle incomplete")
    if not set(SOURCES) <= set(seal.get("sources", {})):
        raise ValueError("Native seal omits original parking source")
    for name, digest in seal["sources"].items():
        source = attempt / name
        if not source.is_file() or sha(source) != digest:
            raise ValueError("sealed original missing or changed: " + name)
    native_exit = read(attempt / "native-exit.json")
    if (native_exit.get("event") != "native_exit" or
            native_exit.get("capture_seal_sha256") != sha(attempt / "capture-seal.json")):
        raise ValueError("Native exit does not bind sealed capture")
    owner = read(attempt / "owner-release.json")
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True
            or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
        raise ValueError("owner release missing or stale")
    provenance_path = attempt / "acquisition-provenance.json"
    if not protocol_fixture:
        provenance = read(provenance_path)
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
            raise ValueError("synthetic diagnostic is not a Native delivery")
    acquisition = read(attempt / "acquisition.json")
    for name in SOURCES[:4]:
        ref = acquisition.get(name, {})
        if ref.get("kind") != "original_native" or ref.get("sha256") != sha(attempt / name):
            raise ValueError("original parking source absent or stale: " + name)
    history, trace, mapping = (rows(attempt / name) for name in
                               ("parking-history.jsonl", "trace.jsonl", "video_frames.jsonl"))
    if (not history or len(history) != len(trace) or len(trace) != len(mapping)
            or len(history) != seal.get("frames")):
        raise ValueError("original parking frame streams incomplete")
    for i, (parking, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get("carla_frame"), video.get("time_s"))
        if (video.get("video_frame") != i or
                (parking.get("frame"), parking.get("time_s")) != identity or
                (motion.get("frame"), motion.get("time_s")) != identity):
            raise ValueError("original parking frame/time join changed")
        if (parking.get("sample_index") != i or
                not isinstance(parking.get("vehicle_vertices"), list) or
                len(parking["vehicle_vertices"]) != 8):
            raise ValueError("original eight-vertex body sample missing")
    context = read(attempt / "parking-context.json")
    cfg = read(attempt / "config.json")
    if (context.get("assignment_id") != ASSIGNMENT or context.get("case_id") != case_id
            or cfg.get("selected_case_id") != case_id or cfg.get("law_id") != "NRS-484B-497"
            or cfg.get("cell_id") != "C229439" or cfg.get("actor") != "vehicle_parker"):
        raise ValueError("original site or case identity differs")
    case = cfg["case"]
    if (context.get("marked_lane_count") != case["requested_marked_lane_count"] or
            context.get("one_way_restriction") != (case["requested_road_direction"] == "one_way") or
            context.get("device_kind") != case["requested_device"]):
        raise ValueError("original statutory construction differs from exact target")
    if not protocol_fixture:
        site_path = attempt / "reviewed-site/site.json"
        if (not site_path.is_file() or context.get("site_sha256") != sha(site_path)
                or acquisition.get("reviewed-site/site.json", {}).get("sha256") != sha(site_path)):
            raise ValueError("reviewed original site packet missing or stale")
        site, records = load_site(site_path, case_id)
        if site.get("requested_activity") != case["requested_activity"] or site.get("requested_side") != case["requested_side"]:
            raise ValueError("reviewed original activity or side differs")
        for ref in site["sources"].values():
            name = "reviewed-site/" + ref["path"]
            if acquisition.get(name, {}).get("sha256") != sha(attempt / name):
                raise ValueError("reviewed original source differs: " + name)
    stationed = [row for row in history if row.get("speed_mps", float("inf")) <= .1 and
                 row.get("control_state") in ("stand", "park", "stop")]
    if not stationed:
        raise ValueError("original stationary vehicle absent")
    forward = context["road_forward_xy"]
    origin = context["road_origin_xy"]
    signed = [(forward[0] * (vertex[1] - origin[1]) - forward[1] * (vertex[0] - origin[0]))
              for row in stationed for vertex in row["vehicle_vertices"]]
    if case["requested_side"] == "left" and max(signed) <= 0:
        raise ValueError("original body did not reach requested left side")
    if case["requested_side"] == "right" and min(signed) >= 0:
        raise ValueError("original body did not reach requested right side")
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
    if result.get("case_id") != case_id or not result.get("physical_checks"):
        raise ValueError("saved physical checks absent or wrong case")
    if not protocol_fixture and not all(result.get(key) is True for key in
                                    ("setup_confirmed", "behavior_attempted", "maneuver_completed")):
        raise ValueError("physical completion not confirmed")
    video = Path(processing.get("analysis_directory", "")) / "raw.mkv"
    if not video.is_file():
        raise ValueError("saved primary video missing")
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(attempt / "video_frames.jsonl"))
    if not protocol_fixture:
        pixel_review = read(attempt / "pixel-review.json")
        if (pixel_review.get("reviewer") in (None, "", "CPU fixture") or
                pixel_review.get("video_sha256") != sha(video) or
                pixel_review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
                not all(pixel_review.get(key) is True for key in
                        ("vehicle_body_visible", "roadway_side_visible", "lane_directions_reviewed",
                         "device_inventory_reviewed", "conduct_reviewed"))):
            raise ValueError("independent actual-pixel and source review missing or stale")
    return {"format": "worker-delivery-audit", "passed": not protocol_fixture,
            "protocol_fixture_checked": protocol_fixture, "case_id": case_id,
            "assignment_id": ASSIGNMENT, "frame_count": len(mapping),
            "native_result_sha256": sha(result_path),
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "video_sha256": sha(video),
            "source_decode_receipt_path": str(decode_receipt),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(__file__),
            "physical_acceptance_claimed": not protocol_fixture,
            "legal_verdict": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--protocol-fixture", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt,
                           args.case, protocol_fixture=args.protocol_fixture), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
