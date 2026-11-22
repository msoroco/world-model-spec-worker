"""C143766 pedestrian Native entrypoint. --check never imports CARLA."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from corridor_construction import validate_scene
from corridor_map import verify_candidate_map
from native_capture import FourVideoRecorder, sample_original_walker
from native_driver import apply_walker_request, spawn_walker

FRAMES = 435


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_scene(scene_path, map_path):
    scene = json.loads(Path(scene_path).read_text())
    validate_scene(scene)
    verified = verify_candidate_map(map_path)
    if scene["map_source_sha256"] != verified["map_sha256"]:
        raise ValueError("scene does not bind exact authored OpenDRIVE")
    return scene


def _trace(actor, sample):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    control = actor.get_control()
    components = [float(v) for v in (pose.location.x, pose.location.y, pose.location.z,
                                     pose.rotation.yaw, velocity.x, velocity.y, velocity.z,
                                     control.direction.x, control.direction.y,
                                     control.direction.z, control.speed)]
    if not all(math.isfinite(value) for value in components):
        raise ValueError("nonfinite original walker telemetry")
    x, y, z, yaw, vx, vy, vz, dx, dy, dz, speed = components
    return {"frame": sample["frame"], "time_s": sample["time_s"],
            "actor_id": sample["actor_id"], "position_m": [x, y, z],
            "position": {"x": x, "y": y, "z": z},
            "heading_deg": yaw, "velocity_mps": [vx, vy, vz],
            "speed_mps": math.sqrt(vx*vx+vy*vy+vz*vz),
            "speed_mph": math.sqrt(vx*vx+vy*vy+vz*vz)/.44704,
            "control": {},
            "walker_control": {"direction_xyz": [dx, dy, dz],
                               "requested_speed_mps": speed,
                               "jump": bool(control.jump)}}


def run_native(scene, scene_path, map_path, output, host, port):
    """Capture one fresh attempt against a caller-owned CARLA endpoint."""
    root = Path(__file__).resolve().parents[2]
    safe_root = (root/".runtime-work").resolve()
    output = Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(safe_root):
        raise ValueError("fresh attempt must be an existing directory under .runtime-work")
    if Path(scene_path).resolve() != output/"scene.json":
        raise ValueError("Native scene must be materialized in the exact attempt")
    if Path(map_path).resolve() != output/"candidate-corridor.xodr":
        raise ValueError("Native map must be materialized in the exact attempt")
    if not (output/"construction.json").is_file() or not (output/"runner.py").is_file():
        raise ValueError("runtime materialized construction and runner required")
    if any((output/name).exists() for name in ("trace.jsonl", "video_frames.jsonl",
                                              "walker-body-history.jsonl", "capture-seal.json")):
        raise ValueError("original acquisition already exists in attempt")
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(safe_root/"c143766-native-runtime")
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore

    client = carla.Client(host, port)
    client.set_timeout(30)
    previous = snapshot_world(client)
    world = None
    actor = None
    videos = None
    frame_map = None
    captured = []
    cleanup = []
    error = None
    restoration = {"restored": False}
    try:
        source = Path(map_path)
        if sha(source) != scene["map_source_sha256"]:
            raise ValueError("authored OpenDRIVE bytes changed before Native loading")
        world = client.generate_opendrive_world(source.read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        actor = spawn_walker(world, scene, carla)
        write(output/"acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "original CARLA walker world vertices and four synchronized RGB sensors",
            "authored_road_sha256": sha(source), "case_id": scene["case_id"]})
        (output/"road.xodr").write_text(world.get_map().to_opendrive())
        videos = FourVideoRecorder(world, scene, carla, output)
        frame_map = FrameMap(output/"video_frames.jsonl")
        target_index = 1
        with (output/"trace.jsonl").open("x", buffering=1) as trace, \
             (output/"walker-body-history.jsonl").open("x", buffering=1) as body, \
             (output/"camera-frame-joins.jsonl").open("x", buffering=1) as joins:
            for _ in range(FRAMES):
                request = apply_walker_request(actor, carla, scene, target_index)
                target_index = request["target_index"]
                frame = world.tick()
                snap = world.get_snapshot()
                if frame != snap.frame:
                    raise RuntimeError("Native world tick/snapshot frame mismatch")
                sample = sample_original_walker(scene, actor, snap)
                join = videos.append(sample)
                frame_map.append(frame, sample["time_s"])
                trace.write(json.dumps(_trace(actor, sample), allow_nan=False)+"\n")
                body.write(json.dumps(sample, allow_nan=False)+"\n")
                joins.write(json.dumps(join, allow_nan=False)+"\n")
                captured.append(frame)
    except BaseException as exc:
        error = repr(exc)
    finally:
        for resource in (frame_map, videos):
            if resource is not None:
                try: resource.close()
                except BaseException as exc: cleanup.append(repr(exc))
        if actor is not None:
            try: actor.destroy()
            except BaseException as exc: cleanup.append(repr(exc))
        try: restoration = restore(client, previous)
        except BaseException as exc: cleanup.append("world restoration: "+repr(exc))
    if error or cleanup or not restoration.get("restored"):
        write(output/"native-run-status.json", {"phase": "failed",
             "errors": [value for value in [error, *cleanup] if value],
             "restoration": restoration, "captured_frames": len(captured)})
        raise RuntimeError("Native pedestrian acquisition or restoration failed")
    sources = ("scene.json", "candidate-corridor.xodr", "road.xodr", "trace.jsonl",
               "walker-body-history.jsonl", "video_frames.jsonl", "camera-frame-joins.jsonl",
               *(name+".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")))
    write(output/"acquisition.json", {name: {"kind": "original_native",
          "sha256": sha(output/name)} for name in sources})
    seal_capture(output, frames=len(captured), restoration=restoration,
                 errors=[], encoder_exit_codes={name: 0 for name in
                 ("overview", "approach", "reference_corner", "driver_reference")},
                 context={"case_id": scene["case_id"],
                          "authored_road_sha256": scene["map_source_sha256"]})
    return {"case_id": scene["case_id"], "frames": len(captured),
            "native_acquisition_sealed": True, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="scene.json")
    parser.add_argument("--map", default="candidate-corridor.xodr")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene = check_scene(args.scene, args.map)
    if args.check:
        print(json.dumps({"case_id": scene["case_id"], "static_construction_valid": True,
                          "planned_frames": FRAMES, "native_started": False}))
    elif args.output_dir:
        print(json.dumps(run_native(scene, args.scene, args.map, args.output_dir,
                                    args.host, args.port)))
    else:
        parser.error("use --check or --output-dir")


if __name__ == "__main__":
    main()
