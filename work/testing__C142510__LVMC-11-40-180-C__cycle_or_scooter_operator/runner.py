"""Source-gated Native runner for one exact connected-sidewalk overtake case.

The local adapter supplies CARLA actor, device, frame and camera acquisition.
This module never treats a synthetic diagnostic as an original capture.
"""

import argparse
import importlib
import json
import os
import math
from pathlib import Path

from native_overtake import build, request_signal
from reviewed_sidewalk import load, require


ASSIGNMENT = "testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def run(config, site, packet_sha256, adapter, output):
    case = config["case"]
    require(case["case_id"] == config["selected_case_id"] and
            case["case_id"] in config["supported_case_ids"] and
            site["rider_kind"] == case["rider_kind"],
            "exact rider case differs from reviewed site")
    offset = config.get("rider_start_offset_m", 0)
    require(type(offset) in (int, float) and offset in (0, 1),
            "unsupported rider approach offset")
    if offset:
        route = site["rider_route_xyz_m"]
        direction = [b - a for a, b in zip(route[0], route[1])]
        length = math.dist(route[0], route[1])
        require(length > 2, "reviewed rider route too short for upstream start")
        site = dict(site)
        site["rider_route_xyz_m"] = [[a - offset * delta / length
                                      for a, delta in zip(route[0], direction)],
                                     *route[1:]]
    built = build(adapter, site)
    try:
        adapter.set_rider_response(built["rider"], case["rider_response"])
        adapter.begin_four_camera_capture(VIEWS, config["cameras"],
                                          built["rider"], built["pedestrian"], output)
        adapter.begin_pedestrian_audio_capture(built["microphone"], output)
        frames = []
        for index in range(config["frame_count"]):
            frame = adapter.tick()
            require(type(frame) is int and
                    (not frames or frame == frames[-1] + 1),
                    "original frame sequence incomplete")
            frames.append(frame)
            if case["signal_frame"] is not None:
                request_signal(adapter, built["emitter"], index,
                               case["signal_frame"])
            adapter.record_actor_and_device_readback(frame, built, output)
        adapter.finish_four_camera_capture(output)
        adapter.finish_pedestrian_audio_capture(output)
        require(len(frames) == 900 and adapter.camera_frame_counts() ==
                {view: 900 for view in VIEWS} and
                adapter.microphone_frame_count() == 900,
                "original camera or microphone capture incomplete")
        return {"case_id": case["case_id"], "reviewed_site_packet_sha256": packet_sha256,
                "first_frame": frames[0], "last_frame": frames[-1],
                "frame_count": len(frames), "physical_acceptance_claimed": False,
                "legal_judgment": None}
    finally:
        for resource in reversed(built["owned"]):
            adapter.destroy(resource)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default=os.getenv("CARLA_HOST"))
    parser.add_argument("--port", default=os.getenv("CARLA_PORT"))
    parser.add_argument("--site-packet", type=Path,
                        default=os.getenv("C142510_SITE_PACKET"))
    parser.add_argument("--source-root", type=Path,
                        default=os.getenv("C142510_SOURCE_ROOT"))
    parser.add_argument("--adapter-module",
                        default=os.getenv("C142510_ADAPTER_MODULE", "native_adapter"))
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    require(config["law_id"] == "LVMC-11-40-180-C" and
            config["cell_id"] == "C142510" and
            config["actor"] == "cycle_or_scooter_operator" and
            config["rate_hz"] == 20 and config["frame_count"] == 900,
            "exact source-gated runner configuration differs")
    if args.check:
        print(config["selected_case_id"])
        return
    require(args.output_dir and args.host and args.port and
            args.site_packet and args.source_root,
            "reviewed original sidewalk, CARLA host/port and output required")
    site, packet_sha256 = load(args.site_packet, args.source_root,
                               config["selected_case_id"])
    module = importlib.import_module(args.adapter_module)
    adapter = module.create_adapter(config, args.host, int(args.port))
    print(json.dumps(run(config, site, packet_sha256, adapter, args.output_dir),
                     sort_keys=True))


if __name__ == "__main__":
    main()
