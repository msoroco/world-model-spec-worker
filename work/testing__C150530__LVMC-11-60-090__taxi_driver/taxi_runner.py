"""Lazy Native entrypoint for the two source-reviewed taxi stand candidates.

No CARLA or pinned pipeline import occurs until a live invocation. The current
worker package has no original reviewed context, so this is CPU construction,
not a runnable delivery claim or a completed pinned compatibility proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from candidate_opendrive import inspect as inspect_xodr
from reviewed_context import validate as validate_context
from stand_route import CASES
from taxi_cameras import CameraCapture, NAMES
from taxi_capture_ticks import capture_ticks
from taxi_native_motion import spawn_taxi, validate_native_map
from native_trace_capture import TraceCapture

ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "runtime" / "SOURCE-MANIFEST.json").is_file():
            return parent
    raise ValueError("pinned worker runtime root unavailable")


def check_static(case: str) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact taxi case")
    folder = Path(__file__).resolve().parent / "candidates"
    map_path = folder / (case + ".xodr")
    layout_path = folder / (case + ".json")
    if not map_path.is_file() or not layout_path.is_file():
        raise ValueError("candidate map or layout absent from bundle")
    inspect_xodr(map_path.read_bytes(), case)
    layout = json.loads(layout_path.read_text())
    if layout.get("case") != case:
        raise ValueError("candidate layout selected another case")
    return {"case_id": ASSIGNMENT + "__" + case,
            "static_construction_valid": True, "native_started": False,
            "map_source_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest()}


def check_materialized_bundle(output: Path, case: str) -> None:
    construction_path = output / "construction.json"
    if not construction_path.is_file():
        raise ValueError("exact materialized construction missing")
    construction = json.loads(construction_path.read_text())
    if construction.get("case_id") != ASSIGNMENT + "__" + case:
        raise ValueError("materialized construction selected another case")
    files = {item["path"]: item["content"] for item in construction.get("files", [])}
    for name in ("config.json", "runner.py", "candidates/" + case + ".xodr",
                 "candidates/" + case + ".json"):
        source = output / name
        if name not in files or not source.is_file() or source.read_text() != files[name]:
            raise ValueError("materialized bundle source missing or changed: " + name)
    config = json.loads((output / "config.json").read_text())
    if config.get("selected_case_id") != ASSIGNMENT + "__" + case:
        raise ValueError("materialized config selected another case")


def check_attempt(output: Path, packet: Path, case: str) -> tuple[Path, Path, Path, Path]:
    output = Path(output).resolve()
    packet = Path(packet).resolve()
    if case not in CASES:
        raise ValueError("unknown exact taxi case")
    if not output.is_dir() or "runtime" in output.parts:
        raise ValueError("fresh Native attempt directory absent or inside frozen runtime")
    if not packet.is_file() or not packet.is_relative_to(output):
        raise ValueError("reviewed context packet must be retained in attempt")
    if any((output / name).exists() for name in
           ("original-trace.jsonl", "original-trace-seal.json", "video_frames.jsonl",
            "overview.mkv", "approach.mkv", "reference_corner.mkv",
            "driver_reference.mkv", "capture-seal.json")):
        raise ValueError("Native attempt was already used")
    folder = output / "candidates" if (output / "construction.json").is_file() else Path(__file__).resolve().parent / "candidates"
    map_path = folder / (case + ".xodr")
    layout_path = folder / (case + ".json")
    inspect_xodr(map_path.read_bytes(), case)
    validate_context(json.loads(packet.read_text()), output, map_path, layout_path)
    return output, packet, map_path, layout_path


def run_native(output: Path, packet: Path, case: str, *, host="127.0.0.1",
               port=2000, blueprint_id="vehicle.tesla.model3") -> dict:
    output, packet, map_path, layout_path = check_attempt(output, packet, case)
    check_materialized_bundle(output, case)
    repo = repository_root()
    runtime_output = (repo / ".runtime-work" / "c150530-pipeline-output").resolve()
    runtime_output.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(runtime_output)
    # Set the output root before any direct pinned pipeline/runtime import.
    sys.path.insert(0, str(repo / "runtime" / "python"))
    sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = None
    taxi = cameras = pipeline = frame_map = trace_writer = None
    captured = None
    restoration = {"restored": False}
    cleanup_errors = []
    try:
        world = client.generate_opendrive_world(map_path.read_text())
        validate_native_map(world, map_path.read_bytes(), case)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        layout = json.loads(layout_path.read_text())
        taxi = spawn_taxi(world, carla, layout, map_path.read_bytes(), blueprint_id)
        cameras = CameraCapture(world, taxi, layout, output, carla)
        pipeline = PipelineCapture(client, taxi, output, ASSIGNMENT + "__" + case)
        frame_map = FrameMap(output / "video_frames.jsonl")
        trace_writer = TraceCapture(output, case, world, taxi, map_path,
                                    layout_path, packet)
        captured = capture_ticks(world, taxi, carla, layout, output, pipeline,
                                 cameras, frame_map, trace_writer)
    finally:
        if trace_writer is not None and not trace_writer.closed:
            try:
                trace_writer.close(completed=False)
            except BaseException as exc:
                cleanup_errors.append(repr(exc))
        for resource in (pipeline, frame_map, cameras):
            if resource is not None:
                try:
                    if resource is pipeline:
                        resource.close(confirmed=captured is not None and
                                       captured["maneuver_completed"])
                    else:
                        resource.close()
                except BaseException as exc:
                    cleanup_errors.append(repr(exc))
        if taxi is not None:
            try:
                taxi.destroy()
            except BaseException as exc:
                cleanup_errors.append(repr(exc))
        try:
            restoration = restore(client, saved_world)
        except BaseException as exc:
            cleanup_errors.append(repr(exc))
    if cleanup_errors or captured is None or not captured["maneuver_completed"] or not restoration.get("restored"):
        raise RuntimeError("Native capture, maneuver or restoration failed: " + "; ".join(cleanup_errors))
    codes = cameras.exit_codes
    if set(codes) != set(NAMES) or any(code != 0 for code in codes.values()):
        raise RuntimeError("original camera encoder exits incomplete or failed")
    seal_capture(output, frames=len(captured["frames"]), restoration=restoration,
                 errors=[], encoder_exit_codes=codes,
                 context={"case_id": ASSIGNMENT + "__" + case,
                          "original_trace_seal": "original-trace-seal.json"})
    return captured


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--context-packet", type=Path)
    parser.add_argument("--case", choices=tuple(CASES))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--blueprint-id", default="vehicle.tesla.model3")
    args = parser.parse_args()
    case = args.case
    if case is None:
        config_path = Path("config.json")
        if not config_path.is_file():
            parser.error("supply --case or materialized config.json")
        selected = json.loads(config_path.read_text()).get("selected_case_id", "")
        case = selected.removeprefix(ASSIGNMENT + "__")
        if case not in CASES or selected != ASSIGNMENT + "__" + case:
            parser.error("materialized config selected another case")
    if args.check:
        print(json.dumps(check_static(case), indent=2))
        return
    output = args.output_dir or args.output
    if output is None:
        parser.error("supply --output-dir for an explicit Native attempt")
    packet = args.context_packet or output / "reviewed-context.json"
    print(json.dumps(run_native(output, packet, case,
                                host=args.host, port=args.port,
                                blueprint_id=args.blueprint_id), indent=2))


if __name__ == "__main__":
    main()
