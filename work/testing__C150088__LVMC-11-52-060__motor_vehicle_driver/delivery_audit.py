"""Independent saved original-source, projection, pixel and lifecycle audit.

The CPU probe uses explicit synthetic_fixture=True. The normal entrypoint
rejects diagnostics and requires original 900-frame source plus pixel review.
"""

import argparse
import hashlib
import json
from pathlib import Path

from projection_construction import CASES
from projection_measurement import measure_packet
from projection_sources import CAMERAS, load_reviewed

ORIGINAL = ("original-projection-history.jsonl", "camera-frame-map.jsonl",
            "trace.jsonl", "video_frames.jsonl", "road.xodr")
VIDEOS = tuple(name + ".mkv" for name in CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def audit(attempt, processing, decode_receipt, case_id, *, synthetic_fixture=False,
          media_verify=None):
    attempt = Path(attempt).resolve()
    processing = Path(processing).resolve()
    decode_receipt = Path(decode_receipt).resolve()
    case = next((item for item in CASES if item.case_id == case_id), None)
    if case is None:
        raise ValueError("unknown exact projection case")
    provenance = read(attempt / "acquisition-provenance.json")
    if synthetic_fixture:
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("CPU probe needs explicit synthetic fixture")
    elif provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("original Native provenance required")
    seal = read(attempt / "capture-seal.json")
    if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("Native capture lifecycle incomplete")
    required = set(ORIGINAL) | set(VIDEOS)
    if not synthetic_fixture:
        required |= {"reviewed-packet/reviewed-site.json", "reviewed-site.json"}
    if not required <= set(seal.get("sources", {})):
        raise ValueError("Native seal omits original projection source")
    for name, digest in seal["sources"].items():
        source = (attempt / name).resolve()
        if not source.is_relative_to(attempt) or not source.is_file() or sha(source) != digest:
            raise ValueError("sealed original missing or changed: " + name)
    native = read(attempt / "native-exit.json")
    if native.get("event") != "native_exit" or native.get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
        raise ValueError("Native exit does not bind capture seal")
    owner = read(attempt / "owner-release.json")
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True or
            owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
        raise ValueError("owner release missing or stale")
    saved = read(processing)
    saved_result = Path(saved.get("result", ""))
    if (saved.get("format") != "worker-saved-processing" or saved.get("passed") is not True or
            saved.get("recorded_only") is not True or saved.get("case_id") != case_id or
            not saved_result.is_file() or saved.get("result_sha256") != sha(saved_result) or
            not saved.get("originals_preserved")):
        raise ValueError("saved-only processing proof absent or changed")
    result = read(saved_result)
    if (result.get("case_id") != case_id or result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or
            result.get("maneuver_completed") is not True):
        raise ValueError("physical parked-assembly completion not confirmed")
    if not synthetic_fixture and result.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic result cannot establish delivery")
    config = read(attempt / "config.json")
    if config.get("selected_case_id") != case_id or config.get("frame_count") != 900:
        raise ValueError("exact 900-frame case configuration required")
    history = rows(attempt / ORIGINAL[0])
    cameras = rows(attempt / ORIGINAL[1])
    trace = rows(attempt / ORIGINAL[2])
    mapping = rows(attempt / ORIGINAL[3])
    count = len(mapping)
    if not history or any(len(item) != count for item in (history, cameras, trace)) or (not synthetic_fixture and count != 900):
        raise ValueError("original complete frame inventory missing")
    measurements = []
    history_sha256 = sha(attempt / ORIGINAL[0])
    for index, (row, camera, point, frame) in enumerate(zip(history, cameras, trace, mapping)):
        native_frame = frame.get("carla_frame")
        if (frame.get("video_frame") != index or row.get("frame") != native_frame or
                point.get("frame") != native_frame or camera.get("native_frame") != native_frame or
                camera.get("camera_frames") != {name: native_frame for name in CAMERAS} or
                abs(row.get("time_s", -1) - frame.get("time_s", -2)) > .002):
            raise ValueError("original projection, trace and four-camera frame join changed")
        packet = dict(row, load_present=case.controlling_part == "load",
                      trailer_attached=case.controlling_part == "trailer")
        measurements.append(measure_packet(packet, {"original-projection-history.jsonl": history_sha256}))
    maximum = max(item["maximum_street_projection_m"] for item in measurements)
    vehicle_base = max(next(part["maximum_street_projection_m"] for part in item["parts"]
                            if part["category"] == "vehicle") for item in measurements)
    controlling = max(measurements, key=lambda item: item["maximum_street_projection_m"])
    controlling_part = max(controlling["parts"], key=lambda item: item["maximum_street_projection_m"])["category"]
    if controlling_part != case.controlling_part:
        raise ValueError("controlling original physical part differs")
    if not synthetic_fixture:
        packet_path = attempt / "reviewed-packet/reviewed-site.json"
        _, reviewed = load_reviewed(packet_path, case_id)
        if read(attempt / "reviewed-site.json") != reviewed:
            raise ValueError("reviewed original curb source differs")
        if any(row.get("reviewed_packet_sha256") != sha(packet_path) or
               row.get("loaded_opendrive_sha256") != reviewed["opendrive_sha256"] for row in history):
            raise ValueError("original loaded map or curb review binding differs")
    video = Path(saved.get("analysis_directory", "")) / "raw.mkv"
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        checker = sha(Path(__file__).with_name("pixel_checks.py"))
        def media_verify(path, receipt, frames, mapping_sha256):
            return verify_receipt(path, receipt, frames,
                                  mapping_sha256=mapping_sha256,
                                  required_checks={"pixel_presence": checker})
    if not video.is_file() or not decode_receipt.is_file():
        raise ValueError("saved video or full source decode missing")
    media_verify(video, decode_receipt, count, sha(attempt / ORIGINAL[3]))
    visibility = read(attempt / "visibility-review.json")
    required_objects = {"curb_line", "vehicle_outer_edge", "controlling_part_outer_edge"}
    if case.controlling_part == "trailer":
        required_objects.add("trailer_hitch")
    if case.controlling_part == "load":
        required_objects.add("load_attachment")
    if (not visibility.get("reviewer") or visibility.get("video_sha256") != sha(video) or
            visibility.get("frame_map_sha256") != sha(attempt / ORIGINAL[3]) or
            not required_objects <= set(visibility.get("visible_objects", []))):
        raise ValueError("source-bound four-camera visibility review missing")
    if not synthetic_fixture and visibility.get("synthetic_fixture") is True:
        raise ValueError("synthetic visibility review cannot accept Native delivery")
    return {"format": "worker-delivery-audit", "passed": True, "case_id": case_id,
            "scope": "synthetic CPU audit proof only" if synthetic_fixture else "original Native delivery review",
            "cell_id": config["cell_id"], "actor": config["actor"],
            "road_sha256": sha(attempt / "road.xodr"),
            "curb_geometry_sha256": hashlib.sha256(json.dumps({key: history[0][key] for key in
                ("curb_segment_start_m", "curb_segment_end_m", "street_side_reference_m")},
                sort_keys=True).encode()).hexdigest(),
            "camera_contract_sha256": hashlib.sha256(json.dumps(config["cameras"], sort_keys=True).encode()).hexdigest(),
            "duration_s": config["duration_s"], "candidate_id": config["candidate_id"],
            "native_result_sha256": sha(saved_result), "frame_count": count,
            "frame_map_sha256": sha(attempt / ORIGINAL[3]), "video_sha256": sha(video),
            "source_decode_receipt_sha256": sha(decode_receipt),
            "maximum_perpendicular_projection_m": maximum,
            "vehicle_base_projection_m": vehicle_base,
            "controlling_part": controlling_part, "statutory_boundary_m": 4.572,
            "construction_tolerance_is_legal_boundary": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("attempt", "processing", "decode-receipt", "case"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt, args.case), indent=2))
