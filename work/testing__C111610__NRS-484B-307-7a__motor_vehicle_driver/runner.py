"""Source gated Native capture for the exact flashing yellow arrow case.

The reviewed site packet supplies a surveyed map, official head identity and a
hash bound adapter. The adapter reads the physical display and camera sensors;
this runner never turns a CARLA traffic-light enum into an arrow observation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

from native_arrow import original, verify_site, construct_native
from native_camera_capture import capture_with_cameras
from native_seal import seal as seal_native

CAMERAS = ["overview", "approach", "reference_corner", "driver_reference"]
VARIANTS = {"arrow_clear", "arrow_ped_crosswalk", "arrow_ped_intersection",
            "arrow_vehicle_intersection", "arrow_concurrent_movement"}


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact arrow plan source changed")
    case_id = config["selected_case_id"]
    matches = [row for row in json.loads(source)["cases"] if row["case_id"] == case_id]
    if (not case_id.startswith(config["assignment_id"] + "__") or len(matches) != 1
            or matches[0]["case_suffix"] != config["case_suffix"]
            or config["case_suffix"] not in VARIANTS
            or config["construction_plan"] != matches[0]["construction"]):
        raise ValueError("Exact arrow case or construction changed")
    if (config["rate_hz"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise ValueError("Original arrow timebase changed")
    if config["cameras"] != CAMERAS:
        raise ValueError("Original four-camera profile changed")
    return case_id


def _adapter(site, root):
    ref_path = site.get("aspect_adapter_source_path")
    refs = [r for r in site["original_sources"] if r["path"] == ref_path]
    if len(refs) != 1 or not ref_path.endswith(".py"):
        raise ValueError("reviewed original aspect and camera adapter source missing")
    path = original(refs[0], root)
    spec = importlib.util.spec_from_file_location("reviewed_c111610_native_adapter", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native adapter cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("bind", "command", "read"):
        if not callable(getattr(module, name, None)):
            raise ValueError("reviewed Native adapter lacks " + name)
    return module


def run_native(root, output, host, port):
    """Tick one sourced world; command then read all five streams per frame."""
    root, output = Path(root).resolve(), Path(output).resolve()
    case_id = check(root)
    source_root = Path(os.environ.get("C111610_SITE_ROOT", str(root))).resolve()
    site_path = source_root / "site.json"
    if not site_path.is_file():
        raise ValueError("reviewed original C111610 site packet missing")
    site = json.loads(site_path.read_text())
    if site.get("case_id") != case_id:
        raise ValueError("reviewed site belongs to another case")
    if site.get("source_kind") != "original_native_site_review":
        raise ValueError("reviewed original Native site provenance missing")
    verify_site(site, source_root)
    adapter = _adapter(site, source_root)
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    settings = world.get_settings()
    previous = (settings.synchronous_mode, settings.fixed_delta_seconds)
    actors = []
    state = None
    receipt = None
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        ego_bp = blueprints.find(site["ego_blueprint_id"])
        kind = site.get("other_kind")
        other_bp = blueprints.find(site["other_blueprint_id"]) if kind else None
        native = construct_native(site, source_root, world, carla, ego_bp, other_bp, kind)
        actors = native["actors"]
        output.mkdir(parents=True, exist_ok=True)
        if source_root != output:
            for ref in site["original_sources"]:
                source = original(ref, source_root)
                destination = (output / ref["path"]).resolve()
                if not destination.is_relative_to(output) or destination.exists():
                    raise ValueError("original site source shadows Native package")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != ref["sha256"]:
                    raise ValueError("original site source changed during capture setup")
            if (output / "site.json").exists():
                raise ValueError("original site packet shadows Native package")
            shutil.copyfile(site_path, output / "site.json")
        state = adapter.bind(world, carla, site, actors, output)

        def step(index):
            adapter.command(state, index)
            frame = world.tick()
            aspect, event, images = adapter.read(state, frame, index)
            if (aspect.get("frame") != frame or event.get("frame") != frame
                    or not isinstance(images, dict)
                    or any(images.get(name, {}).get("frame") != frame for name in CAMERAS)):
                raise ValueError("reviewed Native adapter changed same-tick frame identity")
            return aspect, event, images

        receipt = capture_with_cameras(site, output, step, frames=900)
    finally:
        try:
            if state is not None and callable(getattr(adapter, "close", None)):
                adapter.close(state)
        finally:
            try:
                for actor in reversed(actors):
                    actor.destroy()
            finally:
                settings.synchronous_mode, settings.fixed_delta_seconds = previous
                world.apply_settings(settings)
    restored = world.get_settings()
    if (restored.synchronous_mode, restored.fixed_delta_seconds) != previous:
        raise ValueError("Native world settings restoration readback differs")
    seal_native(output)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print("exact arrow bundle passed: " + check())
    else:
        if not args.output_dir:
            raise ValueError("Native output directory required")
        try:
            run_native(Path(__file__).resolve().parent, args.output_dir, args.host, args.port)
        except BaseException as error:
            output = Path(args.output_dir)
            if output.is_dir() and not (output / "native-run-status.json").exists():
                (output / "native-run-status.json").write_text(json.dumps({
                    "errors": [type(error).__name__ + ": " + str(error)],
                    "capture_finished": False, "physical_acceptance_claimed": False},
                    sort_keys=True) + "\n")
            raise


if __name__ == "__main__":
    main()
