"""Draft C150041 Native entrypoint with source/map and restoration guards.

Only a live CARLA invocation imports the pinned pipeline modules. All original
outputs belong in a fresh attempt under .runtime-work; no physical result is
claimed by this runner itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from parking_cameras import CAMERAS, CameraCapture
from parking_native_driver import spawn_vehicle
from parking_scene import build
from parking_tick_capture import capture_ticks
from source_review import validate


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_native_map(world, packet_path, source_root):
    context = validate(packet_path, source_root=source_root)
    packet = json.loads(Path(packet_path).read_text())
    expected_name = packet["context"].get("native_map_name")
    expected_hash = packet["context"].get("native_opendrive_sha256")
    if not expected_name or not expected_hash:
        raise ValueError("source-reviewed Native map name and OpenDRIVE hash required")
    native_map = world.get_map()
    actual_hash = hashlib.sha256(native_map.to_opendrive().encode()).hexdigest()
    if native_map.name != expected_name or actual_hash != expected_hash:
        raise ValueError("Native map readback differs from source-reviewed map")
    return {**context, "native_map_name": expected_name,
            "native_opendrive_sha256": actual_hash}


def check_materialized_package(output, scene):
    """Reject a missing, mismatched, or already-used attempt before Native capture."""
    output = Path(output)
    for name in ("construction.json", "config.json", "scene.json", "runner.py"):
        if not (output / name).is_file():
            raise ValueError("Native attempt lacks materialized package: " + name)
    if any((output / name).exists() for name in
           ("capture", "trace.jsonl", "parking-history.jsonl", "capture-seal.json")):
        raise ValueError("Native acquisition already started in this attempt")
    package = json.loads((output / "construction.json").read_text())
    config = json.loads((output / "config.json").read_text())
    if (package.get("case_id") != scene["case_id"] or
            config.get("selected_case_id") != scene["case_id"] or
            json.loads((output / "scene.json").read_text()) != scene):
        raise ValueError("Native source-bound scene differs from selected package")


def run_native(packet_path, source_root, suffix, output_dir, *, host="127.0.0.1", port=2000,
               approach_distance_m=8.0):
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    output = Path(output_dir).resolve()
    if not output.is_dir() or not output.is_relative_to(scratch):
        raise ValueError("materialized attempt under .runtime-work required")
    runtime_root = (scratch / "c150041-native-runtime").resolve()
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(runtime_root)
    # Set the pipeline output root before any direct pinned-runtime import.
    sys.path.insert(0, str(repo / "runtime" / "python"))
    sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    scene = build(packet_path, source_root, suffix,
                  approach_distance_m=approach_distance_m)
    check_materialized_package(output, scene)
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    vehicle = None
    cameras = pipeline = frame_map = None
    cleanup_errors = []
    restoration = {"restored": False}
    captured = None
    try:
        check_native_map(world, packet_path, source_root)
        packet_path = Path(packet_path).resolve()
        source_root = Path(source_root).resolve()
        for name, descriptor in json.loads(packet_path.read_text())["sources"].items():
            source = source_root / descriptor["path"]
            relative = Path(descriptor["path"])
            if relative.parts[0] != "reviewed_sources":
                raise ValueError("live reviewed source must reside under reviewed_sources/: " + name)
            target = output / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            if _sha(source) != _sha(target):
                raise ValueError("retained source copy differs: " + name)
        packet_target = output / "reviewed-context.json"
        if not packet_target.exists():
            shutil.copy2(packet_path, packet_target)
        if _sha(packet_path) != _sha(packet_target):
            raise ValueError("retained reviewed packet differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / 20
        world.apply_settings(settings)
        vehicle = spawn_vehicle(world, scene, carla)
        cameras = CameraCapture(world, vehicle, scene, output, carla)
        pipeline = PipelineCapture(client, vehicle, output, scene["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        captured = capture_ticks(world, vehicle, scene, output, carla,
                                 pipeline, cameras, frame_map)
    finally:
        for resource in (pipeline, frame_map, cameras):
            if resource is not None:
                try:
                    if resource is pipeline:
                        resource.close(confirmed=captured is not None)
                    else:
                        resource.close()
                except BaseException as exc:
                    cleanup_errors.append(repr(exc))
        if vehicle is not None:
            try:
                vehicle.destroy()
            except BaseException as exc:
                cleanup_errors.append(repr(exc))
        try:
            restoration = restore(client, saved_world)
        except BaseException as exc:
            cleanup_errors.append(repr(exc))
    if cleanup_errors or captured is None or not restoration.get("restored"):
        raise RuntimeError("Native capture or restoration failed: " + "; ".join(cleanup_errors))
    codes = cameras.exit_codes
    if set(codes) != set(CAMERAS) or any(code != 0 for code in codes.values()):
        raise RuntimeError("Native camera encoder exits incomplete or failed")
    seal_capture(output, frames=len(captured["frames"]), restoration=restoration,
                 errors=[], encoder_exit_codes=codes,
                 context={"case_id": scene["case_id"],
                          "reviewed_packet_sha256": scene["source_packet_sha256"]})
    return captured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--approach-distance-m", type=float, default=8.0)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(build(args.packet, args.source_root, args.case,
                               approach_distance_m=args.approach_distance_m)))
        return
    if not args.output_dir:
        parser.error("use --check or --output-dir")
    run_native(args.packet, args.source_root, args.case, args.output_dir,
               host=args.host, port=args.port,
               approach_distance_m=args.approach_distance_m)


if __name__ == "__main__":
    main()
