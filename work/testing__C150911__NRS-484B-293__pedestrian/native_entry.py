"""Source-gated CARLA acquisition for a reviewed C150911 crosswalk.

Imported only by an explicit local Native run. The operator owns the server.
"""

import hashlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess

from crosswalk_delivery import waypoints
from reviewed_site import load_review, verify_native_map

CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True,
                                     allow_nan=False) + "\n")


def _start_camera(world, carla, name, pose, incoming):
    width, height = CAMERAS[name]
    blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
    blueprint.set_attribute("image_size_x", str(width))
    blueprint.set_attribute("image_size_y", str(height))
    blueprint.set_attribute("sensor_tick", "0.05")
    xyz, pyr = pose["location_xyz_m"], pose["pitch_yaw_roll_deg"]
    transform = carla.Transform(carla.Location(*xyz),
        carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2]))
    sensor = world.try_spawn_actor(blueprint, transform)
    if sensor is None:
        raise RuntimeError("original camera spawn failed: " + name)
    sensor.listen(lambda image: incoming.put(image))
    return sensor


def _encoder(path, width, height):
    return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-c:v", "ffv1", str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _camera_frame(incoming, frame):
    try:
        image = incoming.get(timeout=15)
    except Empty as error:
        raise RuntimeError("synchronized camera frame missing") from error
    if image.frame != frame:
        raise ValueError("original camera frame identity differs")
    return image


def _actor_snapshot(world, walker):
    result = []
    for actor in world.get_actors():
        if actor.id == walker.id or not actor.type_id.startswith(("walker.", "vehicle.")):
            continue
        location = actor.get_location()
        result.append({"actor_id": actor.id, "type_id": actor.type_id,
            "xyz_m": [location.x, location.y, location.z]})
    return result


def _obstacle_width(reviewed, actors, frame, walker_xy, obstructed):
    """Read reviewed fixed obstacle polygons as context, not a legal cutoff."""
    rows = reviewed["source_data"]["obstacles"].get("obstacles")
    if not isinstance(rows, list):
        raise ValueError("reviewed obstacle inventory missing")
    width = reviewed["site"]["crosswalk_width_m"] / 2
    if obstructed and not rows:
        raise ValueError("reviewed obstruction has no original Native obstacle")
    observed = []
    if len(actors) != len(rows):
        raise ValueError("reviewed obstacle construction incomplete")
    for row, actor in zip(rows, actors):
        vertices = row.get("polygon_xy_m")
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise ValueError("reviewed original obstacle polygon missing")
        if actor is None or not actor.is_alive:
            raise ValueError("reviewed obstacle absent in original Native world")
        position = actor.get_location()
        if not any(math.hypot(position.x - x, position.y - y) <= 2 for x, y in vertices):
            raise ValueError("reviewed obstacle moved outside source polygon")
        observed.append({"native_actor_id": actor.id,
                         "xyz_m": [position.x, position.y, position.z]})
        if all(math.dist(walker_xy, point) > 20 for point in vertices):
            continue
        width = min(width, float(row.get("available_right_width_m", width)))
    return {"frame": frame, "source_sha256": reviewed["site"]["obstacle_source_sha256"],
            "available_right_width_m": width, "observed_obstacles": observed}


def run_native(review_path, case_id, output_dir, *, host="127.0.0.1", port=2000,
               speed=1.2):
    """Capture 900 original frames and restore the operator's world on every exit."""
    output = Path(output_dir).resolve()
    allowed = {"config.json", "case-spec.json", "controller.json", "construction.json"}
    if not output.is_dir() or any(p.name not in allowed for p in output.iterdir()):
        raise ValueError("fresh materialized Native attempt directory required")
    reviewed = load_review(review_path, case_id)
    if not 0.3 <= speed <= 1.5:
        raise ValueError("reviewed pedestrian speed outside construction bounds")
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output.parent / "pipeline-output")
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(30)
    prior = snapshot(client)
    sensors, encoders, walker, frame_map, obstacle_actors = {}, {}, None, None, []
    streams = {}
    failure = None
    restored = False
    try:
        world = client.generate_opendrive_world(reviewed["source_data"]["opendrive"])
        verify_native_map(world, reviewed)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        site = reviewed["site"]
        direction = "reverse" if "__reverse_" in case_id else "forward"
        side = "left" if "_left" in case_id else "right"
        if direction == "reverse":
            site = dict(site, entry_center=site["exit_center"],
                        exit_center=site["entry_center"])
        points = waypoints(site, side)
        blueprint = world.get_blueprint_library().filter("walker.pedestrian.*")[0]
        transform = carla.Transform(carla.Location(x=points[0][0], y=points[0][1], z=0.5))
        walker = world.try_spawn_actor(blueprint, transform)
        if walker is None or not walker.type_id.startswith("walker.pedestrian"):
            raise RuntimeError("original pedestrian spawn failed")
        if not walker.is_alive:
            raise RuntimeError("original pedestrian not alive")
        for row in reviewed["source_data"]["obstacles"].get("obstacles", []):
            xyz, pyr = row.get("location_xyz_m"), row.get("pitch_yaw_roll_deg")
            if not isinstance(xyz, list) or len(xyz) != 3 or not isinstance(pyr, list) or len(pyr) != 3:
                raise ValueError("reviewed obstacle Native pose missing")
            obstacle_bp = world.get_blueprint_library().find(row["blueprint_id"])
            actor = world.try_spawn_actor(obstacle_bp,
                carla.Transform(carla.Location(*xyz),
                    carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2])))
            if actor is None:
                raise RuntimeError("reviewed obstacle spawn failed")
            obstacle_actors.append(actor)
        site["pedestrian_source_sha256"] = reviewed["site"]["pedestrian_source_sha256"]
        _write_json(output / "original-site.json", site)
        incoming = {name: Queue() for name in CAMERAS}
        for name, dimensions in CAMERAS.items():
            sensors[name] = _start_camera(world, carla, name,
                reviewed["source_data"]["cameras"][name], incoming[name])
            encoders[name] = _encoder(output / (name + ".mkv"), *dimensions)
        frame_map = FrameMap(output / "video_frames.jsonl")
        for name in ("pedestrian", "obstacles", "participants", "trace"):
            streams[name] = (output / ("original-" + name + ".jsonl" if name != "trace"
                                       else "trace.jsonl")).open("x", buffering=1)
        target = points[-1]
        obstructed = case_id.endswith("_obstructed")
        for index in range(900):
            location = walker.get_location()
            delta = [target[0] - location.x, target[1] - location.y]
            norm = math.hypot(*delta)
            direction_vec = carla.Vector3D(x=delta[0] / max(norm, 1e-9),
                                          y=delta[1] / max(norm, 1e-9), z=0)
            walker.apply_control(carla.WalkerControl(direction=direction_vec,
                                                    speed=speed if norm > 0.2 else 0.0))
            frame = world.tick()
            stamp = world.get_snapshot().timestamp
            time_s = float(stamp.elapsed_seconds)
            frame_map.append(frame, time_s)
            position = walker.get_location()
            xy = [position.x, position.y]
            rows = {
                "pedestrian": {"frame": frame, "elapsed_s": time_s,
                    "pedestrian_id": walker.id,
                    "pedestrian_source_sha256": site["pedestrian_source_sha256"],
                    "pedestrian_xy": xy},
                "obstacles": _obstacle_width(reviewed, obstacle_actors, frame, xy, obstructed),
                "participants": {"frame": frame,
                    "source_sha256": site["participant_source_sha256"],
                    "participants": _actor_snapshot(world, walker)},
                "trace": {"frame": frame, "time_s": time_s,
                    "position_m": [position.x, position.y, position.z],
                    "actor_id": walker.id}}
            for name, row in rows.items():
                streams[name].write(json.dumps(row, allow_nan=False) + "\n")
            for name in CAMERAS:
                image = _camera_frame(incoming[name], frame)
                encoders[name].stdin.write(bytes(image.raw_data))
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError("four-view lossless encoder failed")
        for stream in streams.values():
            stream.close()
        frame_map.close()
        names = ("original-site.json", "original-pedestrian.jsonl",
                 "original-obstacles.jsonl", "original-participants.jsonl")
        _write_json(output / "original-receipt.json", {"case_id": case_id,
            "fps": 20, "frame_count": 900, "diagnostic_fixture": False,
            "review_sha256": reviewed["review_sha256"],
            "sources": {name: _sha(output / name) for name in names}})
    except BaseException as error:
        failure = error
    finally:
        for stream in streams.values():
            if not stream.closed:
                stream.close()
        if frame_map is not None and not frame_map.stream.closed:
            frame_map.close()
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for sensor in sensors.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
        if walker is not None and walker.is_alive:
            walker.destroy()
        for actor in obstacle_actors:
            if actor.is_alive:
                actor.destroy()
        try:
            restored = bool(restore(client, prior)["restored"])
        except BaseException as error:
            failure = failure or error
    _write_json(output / "native-run-status.json", {"restored": restored,
        "capture_complete": failure is None,
        "errors": [repr(failure)] if failure else []})
    if failure or not restored:
        raise RuntimeError("original Native capture or world restoration failed") from failure
    _write_json(output / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": case_id, "review_sha256": reviewed["review_sha256"]})
    seal_capture(output, frames=900, restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={"case_id": case_id, "review_sha256": reviewed["review_sha256"],
                 "legal_verdict_claimed": False})
    return {"case_id": case_id, "review_sha256": reviewed["review_sha256"],
            "frame_count": 900, "restored": True,
            "original_receipt_sha256": _sha(output / "original-receipt.json"),
            "physical_acceptance": False}
