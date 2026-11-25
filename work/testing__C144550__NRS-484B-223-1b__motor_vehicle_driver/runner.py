"""Exact source-gated Native entrypoint for NRS 484B.223(1)(b)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from camera_capture import SIZES
from media_encode import encode
from native_construction import ASSIGNMENT, VARIANTS
from native_session import open_session


HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-223-1b", "C144550", "motor_vehicle_driver"):
        raise ValueError("lane-change assignment identity differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("original 900-frame capture contract differs")
    names = list(SIZES)
    if [(row.get("name"), row.get("width"), row.get("height"))
            for row in config.get("cameras", [])] != [
                (name, *SIZES[name]) for name in names]:
        raise ValueError("four-camera capture profile differs")
    case_id = config.get("selected_case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected lane-change case required")
    if case_id[len(ASSIGNMENT) + 2:] not in VARIANTS:
        raise ValueError("selected controlled lane-change variant differs")
    return config


def run(attempt, host, port, map_packet, map_sha256,
        driver_input_path, driver_input_source_id):
    config = check()
    attempt = Path(attempt).resolve()
    if not attempt.is_dir() or not (attempt / "construction.json").is_file():
        raise ValueError("Native attempt must be materialized by runtime.py capture")
    if not all((map_packet, map_sha256, driver_input_path, driver_input_source_id)):
        raise ValueError("reviewed site and independent driver-input source required")
    with open_session(host, port, map_packet, map_sha256,
                      config["selected_case_id"], driver_input_path,
                      driver_input_source_id) as session:
        source = Path(map_packet)
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != map_sha256:
            raise ValueError("original reviewed map changed before retention")
        retained = attempt / "reviewed-site.json"
        if retained.exists():
            raise ValueError("reviewed original site already retained")
        shutil.copyfile(source, retained)
        receipt = session.capture(attempt)
    if session.restoration is None or not session.restoration.get("restored"):
        raise ValueError("Native world owner release not verified")
    encoder_codes = encode(attempt)
    (attempt / "lane-change-capture-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    names = ("reviewed-site.json", "original-driver-input.jsonl",
             "target-traffic-history.jsonl",
             "readback-inventory.json", "frame_map.json", "ego_pose.json",
             "native_signal.json", "driver_check.json", "video_frames.jsonl",
             "road.xodr", "overview.mkv", "approach.mkv",
             "reference_corner.mkv", "driver_reference.mkv", "raw.mkv")
    (attempt / "acquisition.json").write_text(json.dumps({name: {
        "kind": "original_native", "sha256": hashlib.sha256((attempt / name).read_bytes()).hexdigest()}
        for name in names}, indent=2, sort_keys=True) + "\n")
    from worker_exchange.native_output import seal_capture
    seal_capture(attempt, frames=900, restoration=session.restoration,
                 errors=[], encoder_exit_codes=encoder_codes)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--map-packet", default=os.environ.get("C144550_REVIEWED_MAP_PACKET"))
    parser.add_argument("--map-sha256", default=os.environ.get("C144550_REVIEWED_MAP_SHA256"))
    parser.add_argument("--driver-input-path", default=os.environ.get("C144550_DRIVER_INPUT_PATH"))
    parser.add_argument("--driver-input-source-id", default=os.environ.get("C144550_DRIVER_INPUT_SOURCE_ID"))
    args = parser.parse_args()
    if args.check:
        config = check()
        print(json.dumps({"case_id": config["selected_case_id"],
                          "static_construction_valid": True, "native_started": False}))
    elif args.output_dir:
        run(args.output_dir, args.host, args.port, args.map_packet, args.map_sha256,
            args.driver_input_path, args.driver_input_source_id)
    else:
        parser.error("use --check or --output-dir")


if __name__ == "__main__":
    main()
