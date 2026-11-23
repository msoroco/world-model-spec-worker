"""Portable C153046 red-left construction entrypoint."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from build_case_plan import KINDS
from red_left_turn_controller import Observation
from native_runner import run


def capture_original(output_dir: Path, host: str, port: int, site_packet: Path) -> dict:
    """Connect to a Native host and write original data only under .runtime-work."""
    import carla
    from native_capture import capture

    output_dir = Path(output_dir).resolve()
    packet = Path(site_packet).resolve()
    config = json.loads((output_dir / "config.json").read_text())
    suffix = config["selected_case_id"].rsplit("__", 1)[-1]
    if suffix not in KINDS or config["case"]["case_id"] != config["selected_case_id"]:
        raise ValueError("exact case binding differs")
    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    previous = copy.copy(world.get_settings())
    settings = copy.copy(previous)
    settings.synchronous_mode = True
    settings.no_rendering_mode = False
    settings.fixed_delta_seconds = .05

    def transform(location, rotation):
        return carla.Transform(carla.Location(*location), carla.Rotation(*rotation))

    try:
        world.apply_settings(settings)
        return capture(world, packet, suffix, output_dir, transform,
                       carla.VehicleControl, carla.WalkerControl, carla.Vector3D)
    finally:
        world.apply_settings(previous)


def check() -> None:
    config = json.loads(Path("config.json").read_text())
    case_id = config["selected_case_id"]
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in KINDS or config["case"]["case_id"] != case_id:
        raise ValueError("exact case binding differs")
    if config["law_id"] != "NRS-484B-307-8c" or config["cell_id"] != "C153046":
        raise ValueError("law or cell binding differs")
    if config.get("capture_provenance") != "original Native samples required":
        raise ValueError("capture provenance requirement absent")
    cameras = config.get("cameras", [])
    if [(item.get("name"), item.get("width"), item.get("height")) for item in cameras] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("four-view original capture plan differs")
    from tempfile import TemporaryDirectory
    from tests.test_source_bound_scene import fixture
    from source_bound_scene import sha
    with TemporaryDirectory() as temp:
        root = Path(temp)
        packet = fixture(root)
        if KINDS[suffix][2] == "two_way":
            packet["receiving"]["one_way_to_left"] = False
        path = root / "site.json"
        path.write_text(json.dumps(packet))
        class Actor:
            def __init__(self):
                self.controls = []
            def apply_control(self, control):
                self.controls.append(control)
        actor = Actor()
        samples = [Observation(0, 4, 2, "steady_red_alone", False, False),
                   Observation(1, 1, 0, "steady_red_alone", False, False),
                   Observation(1.5, 1, 0, "steady_red_alone", False, False)]
        result = run(actor, samples, packet_path=path, case_suffix=suffix,
                     control_factory=lambda **kwargs: kwargs, output_path=root / "trace.jsonl")
        if result["samples"] != 3 or len(actor.controls) != 3 or result["source_packet_sha256"] != sha(path):
            raise ValueError("control/capture check failed")
        rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        if any(row["physical_realization_claimed"] for row in rows):
            raise ValueError("CPU check claimed physical realization")
    print("portable exact-case source binding and control application passed:", case_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--site-packet", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check()
    elif args.output_dir:
        packet = args.site_packet or args.output_dir / "site.json"
        if not packet.is_file():
            parser.error("reviewed source-cited site.json required in the output directory")
        print(json.dumps(capture_original(args.output_dir, args.host, args.port, packet)))
    else:
        parser.error("--check or --output-dir required")
