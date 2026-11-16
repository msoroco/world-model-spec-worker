"""Exact C10301 Native capture. CARLA is imported only for explicit capture.

The operator supplies source-reviewed corridor and camera transforms in config.
No legal result is emitted by the capture process; saved processing owns the
source-bound finalizer and independent acceptance audit.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from capture_sources import record_sample
from native_drive import NativeDrive, construct_vehicle, validate_context


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def check_config(config):
    for key in ("selected_case_id", "law_id", "cell_id", "actor", "duration_s",
                "fps", "rate_hz", "requested_speed_mph", "camera_transforms", "corridor_context",
                "recording_description"):
        if config.get(key) in (None, ""):
            raise ValueError("Missing exact capture config: " + key)
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-600-1e", "C10301", "motor_vehicle_driver"):
        raise ValueError("Wrong frozen law/cell/actor")
    if config["fps"] != 20 or config["rate_hz"] != 20 or type(config["duration_s"]) not in (int, float) or not 1 <= config["duration_s"] <= 180:
        raise ValueError("Invalid 20 Hz capture duration")
    target = config["requested_speed_mph"]
    if type(target) not in (int, float) or not math.isfinite(target) or target <= 0:
        raise ValueError("Invalid requested speed")
    transforms = config["camera_transforms"]
    if set(transforms) != set(SIZES):
        raise ValueError("All four named source-camera transforms required")
    for name, pose in transforms.items():
        if not isinstance(pose, dict) or set(pose) != {"location", "rotation"}:
            raise ValueError("Source-camera pose required: " + name)
        location, rotation = pose["location"], pose["rotation"]
        if set(location) != {"x", "y", "z"} or set(rotation) != {"pitch", "yaw", "roll"}:
            raise ValueError("Complete source-camera pose required: " + name)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (*location.values(), *rotation.values())):
            raise ValueError("Finite source-camera pose required: " + name)
    validate_context(config["corridor_context"])
    return config


def _transforms(carla, poses):
    return {name: carla.Transform(carla.Location(**pose["location"]),
                                  carla.Rotation(**pose["rotation"]))
            for name, pose in poses.items()}


def _joined_frame(queue, tick):
    try:
        frame = queue.get(timeout=15)
        while frame.frame < tick:
            frame = queue.get(timeout=15)
    except Empty as error:
        raise ValueError("Missing source-camera frame for Native tick") from error
    if frame.frame != tick:
        raise ValueError("Source-camera frame/tick join failed")
    return frame


def capture(client, carla, config, output):
    """Capture original sources into an already materialized fresh attempt."""
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check_config(config)
    output = Path(output)
    if not (output / "construction.json").is_file() or not (output / "runner.py").is_file():
        raise ValueError("Materialized exact construction required")
    if any((output / name).exists() for name in ("capture-seal.json", "result.json", "video_frames.jsonl")):
        raise ValueError("Retain prior acquisition; choose a fresh attempt")
    saved = snapshot(client)
    world = client.get_world()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    capture_error = None
    restored = False
    try:
        with construct_vehicle(world, config["corridor_context"]) as (vehicle, corridor):
            drive = NativeDrive(corridor, config["requested_speed_mph"], carla.VehicleControl)
            camera_queues = {name: Queue() for name in SIZES}
            transforms = _transforms(carla, config["camera_transforms"])
            context = dict(config["corridor_context"], subject_actor_id=vehicle.id,
                           road_id=corridor["road_id"], lane_id=corridor["lane_id"],
                           measured_corridor_length_m=corridor["measured_length_m"])
            _write(output / "road_context.json", context)
            with ExitStack() as stack:
                sensors = stack.enter_context(source_cameras(world, vehicle, transforms))
                for name, sensor in sensors.items():
                    sensor.listen(camera_queues[name].put)
                writers = {name: stack.enter_context(FFV1Writer(output / (name + ".mkv"), *SIZES[name]))
                           for name in SIZES}
                frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                motion = stack.enter_context((output / "subject_motion.jsonl").open("x"))
                joins = stack.enter_context((output / "camera_joins.jsonl").open("x"))
                pipeline = PipelineCapture(client, vehicle, output, config["selected_case_id"],
                                           required_observations=config.get("required_atoms", []))
                confirmed = False
                try:
                    for _ in range(round(config["duration_s"] * 20)):
                        drive_state = drive.step(vehicle)
                        tick = world.tick()
                        snap = world.get_snapshot()
                        if tick != snap.frame:
                            raise ValueError("Native world tick/snapshot join failed")
                        joined = {}
                        for name in SIZES:
                            frame = _joined_frame(camera_queues[name], tick)
                            image = bytes(frame.raw_data)
                            writers[name].write(image)
                            joined[name] = {"frame": frame.frame,
                                            "bgra_sha256": hashlib.sha256(image).hexdigest()}
                        pipeline.capture(tick, snap.timestamp.elapsed_seconds)
                        measured = record_sample(frame_map, motion, None, vehicle, snap)
                        joins.write(json.dumps({"frame": tick, "time_s": snap.timestamp.elapsed_seconds,
                                                "video_frame": measured["video_frame"],
                                                "source_cameras": joined, "drive_state": drive_state},
                                               allow_nan=False) + "\n")
                    confirmed = True
                finally:
                    pipeline.close(confirmed=confirmed)
    except Exception as error:
        capture_error = error
    finally:
        try:
            restore(client, saved)
            restored = True
        except Exception as error:
            if capture_error is None:
                capture_error = error
            else:
                capture_error = RuntimeError(str(capture_error) + "; restoration: " + str(error))
    if capture_error is not None:
        _write(output / "native-run-status.json", {"errors": [str(capture_error)],
                                                    "restoration_verified": restored})
        raise capture_error
    acquisition = json.loads((output / "capture/manifest.json").read_text())
    expected_frames = round(config["duration_s"] * 20)
    if acquisition.get("extraction_confirmed") is not True or acquisition.get("frames") != expected_frames:
        error = ValueError("Original graph/recorder extraction incomplete")
        _write(output / "native-run-status.json", {"errors": [str(error)],
                                                    "restoration_verified": restored})
        raise error
    original_names = ("config.json", "road_context.json", "video_frames.jsonl",
                      "subject_motion.jsonl", "trace.jsonl", "camera_joins.jsonl",
                      "capture/evidence.jsonl", "capture/manifest.json", "road.xodr",
                      *(name + ".mkv" for name in SIZES))
    for name in ("carla_recorder.log", "capture/recorder_info.txt"):
        if (output / name).is_file():
            original_names += (name,)
    original_names = tuple(dict.fromkeys((*original_names, *(str(path.relative_to(output))
                    for path in (output / "capture").rglob("*") if path.is_file()))))
    _write(output / "capture-seal.json", {
        "events": ["capture_finished", "encoders_closed", "restoration_verified"],
        "sources": {name: _sha(output / name) for name in original_names},
        "native_revision": {"construction_sha256": _sha(output / "construction.json"),
                            "runner_sha256": _sha(output / "runner.py")},
        "frame_count": expected_frames,
        "source_camera_names": list(SIZES), "physical_acceptance_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    root = Path(args.output_dir or ".")
    config = check_config(json.loads((root / "config.json").read_text()))
    if args.check:
        return
    if not args.output_dir:
        raise ValueError("Capture requires --output-dir")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    capture(client, carla, config, root)


if __name__ == "__main__":
    main()
