"""Verify a sealed original backing attempt before saved measurements.

The four media hashes prove source identity, not video pixels or visibility.
This module neither imports CARLA nor supplies a legal judgment.
"""
import argparse
import hashlib
import json
from pathlib import Path

from backing_geometry import validate as validate_geometry, pedestrian_in_reverse_corridor
from backing_measurements import measure
from backing_semantics import response_witness


ASSIGNMENT = "testing__C111301__NRS-484B-113-3__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__pedestrian_yield", ASSIGNMENT + "__pedestrian_continue"}
CAMERAS = ("front", "rear", "left", "right")


def _sealed(root, ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("sealed path and hash required")
    base = Path(root).resolve()
    candidate = (base / ref["path"]).resolve()
    if candidate == base or base not in candidate.parents or not candidate.is_file():
        raise ValueError("sealed source must be a file inside attempt")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if digest != ref["sha256"]:
        raise ValueError("sealed source hash differs: " + ref["path"])
    return candidate


def _json(root, ref):
    return json.loads(_sealed(root, ref).read_text(encoding="utf-8"))


def process(attempt, expected_case):
    if expected_case not in CASES:
        raise ValueError("unknown exact backing case")
    root = Path(attempt).resolve()
    receipt = json.loads((root / "acquisition.json").read_text(encoding="utf-8"))
    if receipt.get("assignment_id") != ASSIGNMENT or receipt.get("case_id") != expected_case:
        raise ValueError("acquisition exact-case identity differs")
    if receipt.get("source_kind") != "native_original" or receipt.get("diagnostic") is not False:
        raise ValueError("original Native acquisition required")
    packet = _json(root, receipt.get("map_packet"))
    map_source = packet.get("map_source")
    map_path = _sealed(root, map_source)
    if hashlib.sha256(map_path.read_bytes()).hexdigest() != packet.get("map_sha256"):
        raise ValueError("original map bytes differ from declared map source")
    geometry = validate_geometry(packet)
    telemetry = _json(root, receipt.get("telemetry"))
    frame_map = _json(root, receipt.get("frame_map"))
    if not isinstance(telemetry, list) or len(telemetry) != 900:
        raise ValueError("900 original telemetry frames required")
    if not isinstance(frame_map, list) or len(frame_map) != 900:
        raise ValueError("900 original frame-map rows required")
    names = receipt.get("media")
    if not isinstance(names, dict) or set(names) != set(CAMERAS):
        raise ValueError("four sealed media sources required")
    media_hashes = {}
    for name in CAMERAS:
        ref = names[name]
        _sealed(root, ref)
        media_hashes[name] = ref["sha256"]
    prior_time = None
    for index, (source, mapping) in enumerate(zip(telemetry, frame_map)):
        if not isinstance(source, dict) or not isinstance(mapping, dict):
            raise ValueError("original frame row required")
        if source.get("frame") != mapping.get("frame") or source.get("frame") != index:
            raise ValueError("original frame identity differs")
        now = source.get("time_s")
        if not isinstance(now, (float, int)) or (prior_time is not None and abs(now - prior_time - .05) > .001):
            raise ValueError("original 20 Hz time continuity differs")
        prior_time = now
        if set(mapping.get("cameras", {})) != set(CAMERAS):
            raise ValueError("four camera frames required per original tick")
        if any(mapping["cameras"][name] != index for name in CAMERAS):
            raise ValueError("camera frame identity differs")
        corridor = pedestrian_in_reverse_corridor(packet, source.get("pedestrian_xy"))
        if type(source.get("pedestrian_in_corridor")) is not bool or source["pedestrian_in_corridor"] != corridor["in_corridor"]:
            raise ValueError("original pedestrian corridor flag differs from source geometry")
    measured = measure(telemetry, source_id=receipt.get("source_id"),
                       map_sha256=geometry["map_sha256"],
                       vehicle_actor_id=receipt.get("vehicle_actor_id"),
                       pedestrian_actor_id=receipt.get("pedestrian_actor_id"))
    witness = response_witness(measured, case_id=expected_case)
    return {"format": "saved-backing-measurement-v1", "assignment_id": ASSIGNMENT,
            "case_id": expected_case, "source_id": receipt["source_id"],
            "acquisition_sha256": hashlib.sha256((root / "acquisition.json").read_bytes()).hexdigest(),
            "map_sha256": geometry["map_sha256"], "frame_count": len(telemetry),
            "map_source": map_source,
            "media_sha256": media_hashes, "measurement": measured,
            "response_witness": witness,
            "corridor_basis": "original_map_reverse_route_and_original_pedestrian_position",
            "full_video_decode": False, "actual_pixels": False,
            "physical_completion": False, "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = process(args.attempt, args.case)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
