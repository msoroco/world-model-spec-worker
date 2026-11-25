"""Exact LVMC 11.16.040 Native handoff for one reviewed intersection case."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

from native_case_runner import run_case_with_reviewed_route

ASSIGNMENT = "testing__C111278__LVMC-11-16-040__motor_vehicle_driver"
CASES = {"blocked_below", "blocked_at", "blocked_above", "clear_at",
         "through_blocked", "controlled_blocked"}


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / "config.json").read_text())
    raw = (root / "case-plan.json").read_bytes()
    if config.get("assignment_id") != ASSIGNMENT or config.get("plan_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("Exact C111278 plan identity or hash differs")
    suffix = config.get("case_key")
    case_id = ASSIGNMENT + "__" + suffix if suffix in CASES else None
    plan = json.loads(raw)
    rows = [row for row in plan["cases"] if row["case_id"] == case_id]
    if (len(rows) != 1 or config.get("selected_case_id") != case_id or
            rows[0]["requested_traversal_speed_mph"] != config.get("requested_traversal_speed_mph") or
            rows[0]["requested_occluder"] != config.get("requested_occluder") or
            rows[0]["through_designation"] != config.get("through_designation") or
            rows[0]["traffic_controlled_intersection"] != config.get("traffic_controlled_intersection")):
        raise ValueError("Exact C111278 selected case changed")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("Original C111278 timebase changed")
    if config.get("controller_gain") not in (1.0, 0.75):
        raise ValueError("unreviewed C111278 controller gain")
    expected = ["overview", "approach", "reference_corner", "driver_reference"]
    if [item.get("name") for item in config.get("cameras", [])] != expected:
        raise ValueError("Original C111278 four-camera inventory changed")
    return case_id


def _reviewed_adapter(source_root: Path, packet: dict):
    ref = packet.get("source_files", {}).get("native_adapter")
    if not isinstance(ref, dict):
        raise ValueError("reviewed original C111278 Native adapter source missing")
    name = ref.get("path")
    if not isinstance(name, str) or not name.endswith(".py") or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("unsafe reviewed Native adapter path")
    source = (source_root / name).resolve()
    if not source.is_relative_to(source_root) or hashlib.sha256(source.read_bytes()).hexdigest() != ref.get("sha256"):
        raise ValueError("reviewed Native adapter source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_c111278_native_adapter", source)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native adapter cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "bind", None)):
        raise ValueError("reviewed Native adapter needs bind")
    return module


def run_native(output: Path, host: str, port: int):
    root = Path(__file__).resolve().parent
    case_id = check(root)
    config = json.loads((root / "config.json").read_text())
    source_root = Path(os.environ.get("C111278_SITE_ROOT", str(root))).resolve()
    packet_path = source_root / "site.json"
    if not packet_path.is_file():
        raise ValueError("reviewed original C111278 site packet missing")
    packet = json.loads(packet_path.read_text())
    if packet.get("selected_case_id") != case_id:
        raise ValueError("reviewed C111278 site belongs to another selected case")
    adapter = _reviewed_adapter(source_root, packet)
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    settings = world.get_settings()
    original = (settings.synchronous_mode, settings.fixed_delta_seconds)
    bound = None
    try:
        settings.synchronous_mode, settings.fixed_delta_seconds = True, 0.05
        world.apply_settings(settings)
        bound = adapter.bind(world, carla, packet, config, output)
        required = ("ego", "camera_adapter", "brake", "control_factory", "location_factory")
        if not isinstance(bound, dict) or any(key not in bound for key in required):
            raise ValueError("reviewed Native adapter binding incomplete")
        receipt = run_case_with_reviewed_route(
            case_key=config["case_key"], packet_path=packet_path, world=world,
            ego=bound["ego"], ray_reader=None, brake=bound["brake"],
            camera_adapter=bound["camera_adapter"], output=output,
            control_factory=bound["control_factory"],
            location_factory=bound["location_factory"],
            controller_gain=config["controller_gain"])
        output = Path(output).resolve()
        for name in ("site.json", *[ref["path"] for ref in packet["source_files"].values()]):
            source = (source_root / name).resolve()
            destination = (output / name).resolve()
            if not source.is_relative_to(source_root) or not destination.is_relative_to(output) or destination.exists():
                raise ValueError("reviewed source cannot be copied into Native output")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        return receipt
    finally:
        try:
            if bound is not None and callable(getattr(adapter, "close", None)):
                adapter.close(bound)
        finally:
            settings.synchronous_mode, settings.fixed_delta_seconds = original
            world.apply_settings(settings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print("exact C111278 bundle passed: " + check())
        return
    if args.output_dir is None:
        raise ValueError("Native output directory required")
    run_native(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
