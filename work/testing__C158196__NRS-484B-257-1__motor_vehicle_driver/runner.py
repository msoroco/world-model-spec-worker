"""Source-gated CARLA entrypoint for the exact C158196 nearest-view cases.

The local operator must supply a reviewed original site packet and source-hashed
Native adapter. No diagnostic site or assumed signal/sign state can start CARLA.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from construction import verify_site_sources
from native_capture import encode_original_cameras, seal

ASSIGNMENT = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver"
CASES = {"nearest_view_hold", "nearest_view_continue", "nearest_view_clear",
         "active_signal_exception"}


def check(root: Path | None = None) -> dict:
    root = Path(root or Path(__file__).resolve().parent).resolve()
    config = json.loads((root / "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-257-1" or
            config.get("cell_id") != "C158196" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("exact C158196 runner identity differs")
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("frame_count")) != (20, 45, 900):
        raise ValueError("exact original timebase differs")
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            case_id.rsplit("__", 1)[1] not in CASES or
            case_id not in config.get("supported_case_ids", [])):
        raise ValueError("exact selected case differs")
    source = (root / "frozen-assignment.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config.get("input_sha256"):
        raise ValueError("frozen assignment source changed")
    if json.loads(source).get("assignment_id") != ASSIGNMENT:
        raise ValueError("frozen assignment identity differs")
    return config


def _adapter(site: dict, source_root: Path):
    entry = site.get("native_adapter_source")
    if not isinstance(entry, dict) or entry.get("origin") != "original_native":
        raise ValueError("reviewed original Native adapter source required")
    relative = entry.get("path")
    if not isinstance(relative, str) or not relative.endswith(".py") or Path(relative).is_absolute():
        raise ValueError("reviewed Native adapter path invalid")
    path = (source_root / relative).resolve()
    if not path.is_relative_to(source_root) or not path.is_file():
        raise ValueError("reviewed Native adapter source missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
        raise ValueError("reviewed Native adapter source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_c158196_native_adapter", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native adapter cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("bind", "tick", "close"):
        if not callable(getattr(module, name, None)):
            raise ValueError("reviewed Native adapter lacks " + name)
    return module


def run_native(root: Path, output: Path, host: str, port: int) -> dict:
    root, output = Path(root).resolve(), Path(output).resolve()
    config = check(root)
    case = config["selected_case_id"].rsplit("__", 1)[1]
    source_root = Path(os.environ.get("C158196_SITE_ROOT", str(root))).resolve()
    site_path = source_root / "site.json"
    if not site_path.is_file():
        raise ValueError("reviewed original C158196 site packet missing")
    site = json.loads(site_path.read_text())
    if (site.get("source_kind") != "original_native_site_review" or
            site.get("assignment_id") != ASSIGNMENT or
            site.get("case_id") != config["selected_case_id"]):
        raise ValueError("reviewed original site identity differs")
    verify_site_sources(site, case, source_root)
    adapter = _adapter(site, source_root)
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    settings = world.get_settings()
    previous = (settings.synchronous_mode, settings.fixed_delta_seconds)
    state = None
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        state = adapter.bind(world, carla, site, config, output)
        if state is None:
            raise ValueError("reviewed Native adapter did not bind actors and cameras")
        receipt = seal(site, case, source_root, output,
                       lambda index: adapter.tick(state, index), frames=900)
    finally:
        try:
            if state is not None:
                adapter.close(state)
        finally:
            settings.synchronous_mode, settings.fixed_delta_seconds = previous
            world.apply_settings(settings)
    restored = world.get_settings()
    if (restored.synchronous_mode, restored.fixed_delta_seconds) != previous:
        raise ValueError("Native world settings restoration readback differs")
    encode_original_cameras(output)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print("exact C158196 bundle passed: " + check()["selected_case_id"])
        return
    if args.output_dir is None:
        raise ValueError("Native output directory required")
    run_native(Path(__file__).resolve().parent, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
