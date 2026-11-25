"""Original Native capture for the two blocked-sidewalk bypass requests."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import traceback

from native_scene import (CAMERAS, FRAMES, RATE_HZ, geometry,
                          apply_control, check, open_drive, request,
                          spawn_obstruction, survey)

HERE = Path(__file__).resolve().parent


def _write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise ValueError("original pedestrian ground footprint missing")
    return [list(point) for point in points]


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    condition = config.get("case_suffix")
    check(condition)
    if condition not in ("condition_a", "condition_b", "direction_east",
                         "direction_west", "bike_passable", "bike_impassable"):
        raise ValueError("exact bypass case required")
    if config.get("law_id") != "NRS-484B-297-6" or config.get("cell_id") != "C109128":
        raise ValueError("frozen law/cell identity changed")
    if config.get("rate_hz") != RATE_HZ or config.get("duration_s") != 30:
        raise ValueError("exact 20 Hz, 30-second capture required")
    output = Path(output).resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("fresh materialized exact Native attempt required")
    if any((output / name).exists() for name in
           ("pedestrian-original.jsonl", "video_frames.jsonl", "result.json")):
        raise ValueError("retain previous original Native attempt")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    old = client.get_world()
    state = snapshot(client)
    if state["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in old.get_actors()):
        raise ValueError("exclusive idle asynchronous Native world required")
    owned, encoders, encoder_logs, image_queues = [], {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    completed = 0
    try:
        world = client.generate_opendrive_world(open_drive(condition), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        (output / "road.xodr").write_text(world.get_map().to_opendrive())
        scene = survey(world, carla, condition)
        obstruction = spawn_obstruction(world, carla, condition,
                                        raise_z_m=config.get("obstruction_raise_z_m", 0.0))
        owned.extend(obstruction)
        scene["obstruction_actors"] = [{"native_actor_id": actor.id,
            "native_type_id": actor.type_id,
            "native_xyz_m": [actor.get_transform().location.x,
                             actor.get_transform().location.y,
                             actor.get_transform().location.z],
            "extent_xyz_m": [actor.bounding_box.extent.x,
                             actor.bounding_box.extent.y,
                             actor.bounding_box.extent.z]} for actor in obstruction]
        scene["obstruction_physical_review_pending"] = True
        scene["sidewalk_context"] = {
            "source_kind": "original_native_map_readback",
            "roadway_lane_count": len(scene["lanes"]["roadway"]),
            "sidewalk_lane_count": len(scene["lanes"]["sidewalk"]),
            "obstruction_actor_count": len(scene["obstruction_actors"]),
            "legal_status_review_pending": True,
        }
        _write(output / "sidewalk_context.json", scene)
        library = world.get_blueprint_library()
        walker_blueprints = sorted(library.filter("walker.pedestrian.*"), key=lambda bp: bp.id)
        if not walker_blueprints:
            raise ValueError("Native pedestrian blueprint absent")
        walker = world.try_spawn_actor(walker_blueprints[0], carla.Transform(
            carla.Location(x=45 if condition == "direction_west" else 5,
                           y=geometry(condition)["sidewalk_center_y"], z=.5),
            carla.Rotation(yaw=0)))
        if walker is None:
            raise ValueError("Native pedestrian spawn failed")
        owned.append(walker)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 90), ("sensor_tick", 1 / RATE_HZ)):
                bp.set_attribute(key, str(value))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            if camera is None:
                raise ValueError("Native source-camera spawn failed: " + name)
            owned.append(camera)
            image_queues[name] = queue.Queue()
            camera.listen(image_queues[name].put)
            encoder_logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                "-r", str(RATE_HZ), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
        capture = PipelineCapture(client, walker, output, config["case_id"],
                                  visibility=False,
                                  required_observations=config.get("required_atoms", []))
        first_time = None
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "pedestrian-original.jsonl").open("x") as people, \
                (output / "camera-sources.jsonl").open("x") as cameras:
            for index in range(FRAMES):
                control = apply_control(walker, carla, config["case_suffix"], index,
                                        config.get("lateral_shift_m", 0.0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise ValueError("Native snapshot and tick differ")
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - first_time
                pose = walker.get_transform().location
                person = {"video_frame": index, "native_frame": native_frame,
                          "time_s": time_s, "walker_id": walker.id,
                          "center_xy_m": [pose.x, pose.y],
                          "footprint_xy_m": _body(walker),
                          "requested_target_xy_m": control["target_xy_m"],
                          "requested_bypass_path": config["case_suffix"],
                          "original_native_observed": True,
                          "physical_or_legal_verdict": None}
                capture.capture(native_frame, time_s,
                                extra={"sidewalk_bypass_observation": person})
                pixel_hashes = {}
                for name, width, height, *_ in CAMERAS:
                    image = image_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = image_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise ValueError("Native camera/frame identity differs: " + name)
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1].tobytes()
                    digest = hashlib.sha256(rgb).hexdigest()
                    pixel_hashes[name] = digest
                    encoders[name].stdin.write(rgb)
                    cameras.write(json.dumps({"camera": name, "video_frame": index,
                        "native_frame": native_frame, "time_s": time_s,
                        "width": width, "height": height,
                        "source_path": name + ".mkv", "source_rgb_sha256": digest}) + "\n")
                person["source_rgb_sha256"] = pixel_hashes
                people.write(json.dumps(person, allow_nan=False) + "\n")
                frame_map.append(native_frame, time_s,
                                 source_rgb_sha256=pixel_hashes)
                completed += 1
        if completed != FRAMES:
            raise ValueError("incomplete original Native capture")
        for name, encoder in encoders.items():
            encoder.stdin.close()
            if encoder.wait(timeout=180) != 0:
                raise ValueError("Native camera encoding failed: " + name)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=False)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                if encoder.poll() is None:
                    encoder.stdin.close()
                    if encoder.wait(timeout=180) != 0:
                        raise ValueError("camera encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"actor_cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, state)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        if output.exists():
            _write(output / "native-capture-report.json", {"frames": completed,
                "expected_frames": FRAMES, "error": error, "restoration": restored,
                "physical_or_legal_acceptance_claimed": False})
    if error:
        raise RuntimeError("Native bypass capture failed; inspect native-capture-report.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        config = json.loads(args.config.read_text())
        print(json.dumps(check(config["case_suffix"]), sort_keys=True))
    else:
        if not args.output_dir:
            raise ValueError("exact config and fresh Native output required")
        execute(json.loads(args.config.read_text()), args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
