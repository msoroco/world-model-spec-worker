"""Portable C153046 red-left construction entrypoint."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil

from build_case_plan import KINDS
from red_left_turn_controller import Observation
from native_runner import run


def stage_reviewed_site(packet_path: Path, output_dir: Path, expected_sha256: str) -> Path:
    """Copy a reviewed, source-checked site packet into a fresh Native attempt."""
    from source_bound_scene import build

    packet_path = Path(packet_path).resolve()
    output_dir = Path(output_dir).resolve()
    if not expected_sha256 or hashlib.sha256(packet_path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("reviewed site packet SHA-256 missing or changed")
    config = json.loads((output_dir / "config.json").read_text())
    suffix = config["selected_case_id"].rsplit("__", 1)[-1]
    build(packet_path, suffix)
    packet = json.loads(packet_path.read_text())
    destination = output_dir / "site.json"
    if destination.exists():
        raise ValueError("retained site packet already exists in Native attempt")
    for descriptor in packet["sources"].values():
        relative = Path(descriptor["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("site source path escapes reviewed packet directory")
        source = (packet_path.parent / relative).resolve()
        target = output_dir / relative
        if target.exists():
            raise ValueError("site source shadows materialized construction")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(packet_path, destination)
    build(destination, suffix)
    return destination


def resolve_site_packet(output_dir: Path, explicit: Path | None = None) -> Path:
    selected = explicit or os.environ.get("C153046_SITE_PACKET")
    if not selected:
        raise ValueError("C153046_SITE_PACKET reviewed source path required")
    return stage_reviewed_site(
        Path(selected), output_dir,
        os.environ.get("C153046_SITE_PACKET_SHA256", ""),
    )


def capture_original(output_dir: Path, host: str, port: int, site_packet: Path) -> dict:
    """Connect to a Native host and write original data only under .runtime-work."""
    import carla
    from native_capture import capture
    from saved_measurement import finalize_attempt
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output_dir = Path(output_dir).resolve()
    packet = Path(site_packet).resolve()
    config = json.loads((output_dir / "config.json").read_text())
    suffix = config["selected_case_id"].rsplit("__", 1)[-1]
    if suffix not in KINDS or config["case"]["case_id"] != config["selected_case_id"]:
        raise ValueError("exact case binding differs")
    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    saved = snapshot(client)
    settings = copy.copy(saved["settings"])
    settings.synchronous_mode = True
    settings.no_rendering_mode = False
    settings.fixed_delta_seconds = .05

    def transform(location, rotation):
        return carla.Transform(carla.Location(*location), carla.Rotation(*rotation))

    errors = []
    acquired = None
    try:
        world.apply_settings(settings)
        acquired = capture(world, packet, suffix, output_dir, transform,
                           carla.VehicleControl, carla.WalkerControl, carla.Vector3D)
    except Exception as error:
        errors.append("capture: " + str(error))
    try:
        restoration = restore(client, saved)
    except Exception as error:
        restoration = {"restored": False}
        errors.append("world restoration: " + str(error))
    if errors:
        (output_dir / "native-run-status.json").write_text(json.dumps({
            "errors": errors, "restoration": restoration,
            "physical_acceptance_claimed": False}, indent=2) + "\n")
        raise ValueError("; ".join(errors))
    try:
        report = finalize_attempt(output_dir, output_dir / "analysis-report.json")
        (output_dir / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "site_packet_sha256": report["measurement"]["site_packet_sha256"],
            "physical_acceptance_claimed": False}, indent=2) + "\n")
        closure = seal_capture(output_dir, frames=acquired["trace"]["samples"],
                               restoration=restoration, errors=[],
                               encoder_exit_codes={name: 0 for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")})
        return {"capture": acquired, "analysis": report["case_id"],
                "seal": closure["format"], "physical_acceptance_claimed": False}
    except Exception as error:
        (output_dir / "native-run-status.json").write_text(json.dumps({
            "errors": ["finalization or seal: " + str(error)],
            "restoration": restoration, "physical_acceptance_claimed": False}, indent=2) + "\n")
        raise


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
        packet = resolve_site_packet(args.output_dir, args.site_packet)
        print(json.dumps(capture_original(args.output_dir, args.host, args.port, packet)))
    else:
        parser.error("--check or --output-dir required")
