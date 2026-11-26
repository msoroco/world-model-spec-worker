"""Exact hose entrypoint; original reviewed sources are mandatory for capture."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from fire_hose_delivery import segment_intersects, Point
from native_capture import capture


def check(root):
    config = json.loads((root / "config.json").read_text())
    case = config["case"]
    if config["selected_case_id"] != config["assignment_id"] + "__" + case["short_id"]:
        raise ValueError("exact hose case identity differs")
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-913", "C197786", "motor_vehicle_driver"):
        raise ValueError("hose law/cell/actor identity differs")
    if (config["frame_count"], config["rate_hz"], config["duration_s"]) != (900, 20, 45):
        raise ValueError("Native capture profile differs")
    if set(config["camera_views"]) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four camera source views differ")
    if case["incident_purpose"] not in ("fire", "alarm", "practice"):
        raise ValueError("qualifying hose incident purpose differs")
    if case["hose_protection"] not in ("unprotected", "protected"):
        raise ValueError("hose protection case differs")
    if case["command_consent"] not in ("none", "given", "withheld"):
        raise ValueError("command consent case differs")
    if config["source_gate"] != "reviewed_original_required":
        raise ValueError("reviewed original source gate differs")
    return config


def reviewed_source(packet_path, source_root, config):
    packet_path = Path(packet_path)
    root = Path(source_root).resolve()
    packet = json.loads(packet_path.read_text())
    if packet.get("case_id") != config["selected_case_id"]:
        raise ValueError("reviewed packet exact case differs")
    if (packet.get("cell_id"), packet.get("law_id")) != ("C197786", "NRS-484B-913"):
        raise ValueError("reviewed packet law/cell differs")
    source_paths = set()
    for key in ("private_way", "hose", "incident", "official", "consent", "vehicle"):
        source = packet.get(key)
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError(key + " reviewed original source missing")
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(key + " reviewed original file unavailable")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(key + " reviewed original hash mismatch")
        if path in source_paths:
            raise ValueError("distinct reviewed original sources required")
        source_paths.add(path)
        original = json.loads(path.read_text())
        expected = {field: value for field, value in source.items() if field not in ("path", "sha256")}
        if original != expected:
            raise ValueError(key + " reviewed original content mismatch")
    hose = packet["hose"]
    if hose.get("fire_department_affiliation") is not True:
        raise ValueError("fire-department hose affiliation unproven")
    if not hose.get("blueprint_id") or "hose" not in hose["blueprint_id"].lower():
        raise ValueError("hose-specific blueprint identity missing")
    if hose.get("protection") != config["case"]["hose_protection"]:
        raise ValueError("hose protection source differs")
    if packet["incident"].get("purpose") != config["case"]["incident_purpose"]:
        raise ValueError("incident purpose source differs")
    if packet["consent"].get("status") != config["case"]["command_consent"]:
        raise ValueError("official consent source differs")
    if not packet["official"].get("in_command") or not packet["official"].get("identity"):
        raise ValueError("command official source unproven")
    if packet["consent"].get("status") == "given" and (
            packet["consent"].get("official_identity") != packet["official"]["identity"]
            or packet["consent"].get("frame") is None or not packet["consent"].get("scope")):
        raise ValueError("command official consent timing or scope unproven")
    if packet["vehicle"].get("ordinary_motor_vehicle") is not True or packet["vehicle"].get("human_driver") is not True:
        raise ValueError("vehicle and human driver source unproven")
    road = packet["private_way"]
    if not road.get("owner") or not road.get("permitted_access"):
        raise ValueError("private way ownership or access unproven")
    path = road.get("ego_route_xy")
    segment = hose.get("segment_xy")
    if not isinstance(path, list) or len(path) < 2 or not isinstance(segment, list) or len(segment) != 2:
        raise ValueError("reviewed route or actual hose segment missing")
    crosses = any(segment_intersects(Point(*a), Point(*b), Point(*segment[0]), Point(*segment[1]))
                  for a, b in zip(path, path[1:]))
    if crosses != config["case"]["planned_hose_crossing"]:
        raise ValueError("reviewed route/hose geometry differs from exact case")
    return packet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviewed-packet", type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    packet_path = args.reviewed_packet or os.environ.get("HOSE_REVIEWED_PACKET")
    source_root = args.source_root or os.environ.get("HOSE_SOURCE_ROOT")
    if not packet_path or not source_root or not args.output_dir or not args.host or not args.port:
        raise ValueError("original reviewed packet, source root, Native server and output required")
    packet = reviewed_source(packet_path, source_root, config)
    adapter_name = os.environ.get("HOSE_NATIVE_ADAPTER", "native_adapter")
    adapter = importlib.import_module(adapter_name).create_adapter(config, args.host, args.port)
    if adapter.provenance() != "original_native":
        raise ValueError("original Native adapter provenance required")
    print(json.dumps(capture(adapter, config, packet, packet_path, source_root, args.output_dir),
                     sort_keys=True))


if __name__ == "__main__":
    main()
