"""Exact C125714 opposing-pass Native entrypoint.

Offline --check validates the bundled case. An original Native run additionally
requires a separately reviewed map packet and its exact SHA256 at launch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from native_session import open_session
from media_encode import encode
from opposing_pass import VARIANTS


HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C125714__NRS-484B-203-1__motor_vehicle_driver"


def check():
    config = json.loads((HERE / "config.json").read_text())
    case = config.get("selected_case_id")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-203-1", "C125714", "motor_vehicle_driver"):
        raise ValueError("opposing-pass assignment scope changed")
    if not isinstance(case, str) or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact opposing-pass case absent")
    variant = case[len(ASSIGNMENT) + 2:]
    if variant not in VARIANTS or config.get("variant") != variant:
        raise ValueError("opposing-pass case variant changed")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("opposing-pass 900-frame capture contract changed")
    expected = (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
    if tuple((row.get("name"), row.get("width"), row.get("height"))
             for row in config.get("cameras", [])) != expected:
        raise ValueError("four original camera contract changed")
    if not config.get("recording_description"):
        raise ValueError("opposing-pass measurement description missing")
    return config


def run(output, host, port, map_packet, map_sha256):
    config = check()
    output = Path(output).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Native attempt must be materialized by runtime.py capture")
    if not map_packet or not map_sha256:
        raise ValueError("separately reviewed original median-opening map source required")
    with open_session(host, port, map_packet, map_sha256, config["variant"],
                      config.get("route_profile", "primary")) as session:
        source = Path(map_packet)
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != map_sha256:
            raise ValueError("original reviewed site changed before source retention")
        retained = output / "reviewed-map.json"
        if retained.exists():
            raise ValueError("reviewed original source already retained")
        shutil.copyfile(source, retained)
        if hashlib.sha256(retained.read_bytes()).hexdigest() != map_sha256:
            raise ValueError("retained original site differs")
        receipt = session.capture(output / "opposing-actor-trace.json",
                                  output / "opposing-camera-frames")
    if not session.restoration_verified:
        raise ValueError("original Native world restoration unverified")
    encoder_codes = encode(output / "opposing-camera-frames", output)
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "reviewed_map_sha256": map_sha256,
        "method": "original 20 Hz CARLA world, actor bodies, four sensor views and PipelineCapture"},
        indent=2, sort_keys=True) + "\n")
    names = ("reviewed-map.json", "opposing-actor-trace.json", "trace.jsonl",
             "video_frames.jsonl", "road.xodr", "carla_recorder.log",
             "overview.mkv", "approach.mkv", "reference_corner.mkv",
             "driver_reference.mkv", "raw.mkv")
    (output / "acquisition.json").write_text(json.dumps({name: {
        "kind": "original_native", "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
        for name in names}, indent=2, sort_keys=True) + "\n")
    (output / "opposing-capture-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=900, restoration={"restored": True,
        "scope": "four cameras and two owned actors destroyed; synchronous settings read back"},
        errors=[], encoder_exit_codes=encoder_codes)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--map-packet", default=os.environ.get("C125714_REVIEWED_MAP_PACKET"))
    parser.add_argument("--map-sha256", default=os.environ.get("C125714_REVIEWED_MAP_SHA256"))
    args = parser.parse_args()
    if args.check:
        config = check()
        print(json.dumps({"case_id": config["selected_case_id"],
                          "static_construction_valid": True, "native_started": False}))
    elif args.output_dir:
        run(args.output_dir, args.host, args.port, args.map_packet, args.map_sha256)
    else:
        parser.error("use --check or --output-dir")


if __name__ == "__main__":
    main()
