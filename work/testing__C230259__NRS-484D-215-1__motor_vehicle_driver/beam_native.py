"""Lazy CARLA capture of original moving-road headlamp sources.

The site packet is source reviewed before CARLA starts. The operator owns every
actor, restores world settings, and preserves original 20 Hz telemetry and
four sensor streams. Physical beam and glare judgments are never inferred from
requested CARLA light bits.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from beam_camera import CameraRecorder, PROFILE_DIMENSIONS, VIEWS, encode_original_videos
from beam_construction import validate_site
from beam_projection import bbox, eye_cube


def _inside(x, y, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _point(carla, point, yaw=0.0):
    return carla.Transform(carla.Location(x=point[0], y=point[1], z=point[2]),
                           carla.Rotation(yaw=yaw))


def _heading(start, end):
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def _center(actor):
    location = actor.get_location()
    return [float(location.x), float(location.y), float(location.z)]


def _radius(actor):
    bounds = actor.bounding_box.extent
    return math.hypot(bounds.x, bounds.y)


def _eye(actor, offset):
    center = _center(actor)
    if len(offset) != 3:
        raise ValueError("reviewed original driver-eye offset required")
    yaw = math.radians(actor.get_transform().rotation.yaw)
    return [center[0] + offset[0] * math.cos(yaw) - offset[1] * math.sin(yaw),
            center[1] + offset[0] * math.sin(yaw) + offset[1] * math.cos(yaw),
            center[2] + offset[2]]


def _route_control(carla, actor, route, index, speed_request):
    location = actor.get_location()
    point = route[min(index + 1, len(route) - 1)]
    target_yaw = math.atan2(point[1] - location.y, point[0] - location.x)
    yaw = math.radians(actor.get_transform().rotation.yaw)
    error = (target_yaw - yaw + math.pi) % (2 * math.pi) - math.pi
    speed = actor.get_velocity().length()
    return carla.VehicleControl(throttle=max(0.0, min(.6, .16 * (speed_request - speed))),
                                brake=max(0.0, min(.8, .25 * (speed - speed_request))),
                                steer=max(-.7, min(.7, .75 * error)))


def _requested_lights(carla, mode):
    if mode == "off":
        return carla.VehicleLightState.NONE
    if mode == "low":
        return carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam
    if mode == "high":
        return carla.VehicleLightState.Position | carla.VehicleLightState.HighBeam
    raise ValueError("unknown requested beam")


def _sensor(carla, world, library, ego, spec, view):
    blueprint = library.find("sensor.camera.rgb")
    width, height = PROFILE_DIMENSIONS[view]
    blueprint.set_attribute("image_size_x", str(width))
    blueprint.set_attribute("image_size_y", str(height))
    blueprint.set_attribute("sensor_tick", "0.05")
    blueprint.set_attribute("fov", str(spec["fov_deg"]))
    # Reviewed local mount uses position and Euler angles. CARLA confirms the
    # resulting original camera frame through the synchronized recorder.
    transform = carla.Transform(
        carla.Location(*spec["transform_m"]),
        carla.Rotation(pitch=spec.get("pitch_deg", 0),
                       yaw=spec.get("yaw_deg", 0), roll=spec.get("roll_deg", 0)))
    sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
    if sensor is None:
        raise ValueError("original camera spawn failed: " + view)
    return sensor


def capture(client, packet_path: Path, output: Path, case: dict, *, ticks: int = 900,
            camera_pose_selection: str = "primary") -> dict:
    """Capture a fresh attempt; call only through runtime.py capture on a GPU host."""
    from worker_exchange.world_restore import snapshot, restore
    from pipeline_capture import PipelineCapture
    import carla

    site = validate_site(packet_path, case, diagnostic=False)
    if camera_pose_selection == "primary":
        camera_specs = site["cameras"]
    elif camera_pose_selection == "alternate" and site.get("alternate_cameras"):
        camera_specs = site["alternate_cameras"]
    else:
        raise ValueError("source-reviewed selected camera pose set missing")
    if ticks != 900:
        raise ValueError("selected delivery requires 900 original frames")
    output = Path(output)
    originals = ("actor-state.jsonl", "camera-frame-map.jsonl", "roi-frames.jsonl",
                 "trace.jsonl", "video_frames.jsonl", "native-source-receipt.json",
                 "site-packet.json")
    if output.exists() and any((output / name).exists() for name in originals):
        raise ValueError("Native output already contains original source files")
    world = client.get_world()
    native_map = world.get_map()
    if native_map.name != site["map_name"] or hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() != site["map_sha256"]:
        raise ValueError("loaded Native map differs from reviewed source")
    saved = snapshot(client)
    owned = []
    recorder = None
    pipeline = None
    completed = False
    try:
        settings = copy.copy(world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or abs(readback.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native synchronous 20 Hz settings did not read back")
        library = world.get_blueprint_library()
        actors = {}
        for role in ("ego", "oncoming"):
            route = site["routes"][role]
            blueprint = library.find(site["blueprints"][role])
            actor = world.try_spawn_actor(blueprint, _point(carla, route[0], _heading(route[0], route[1])))
            if actor is None:
                raise ValueError("Native vehicle spawn failed: " + role)
            actors[role] = actor
            owned.append(actor)
        for role in ("person", "vehicle"):
            target = site["targets"][role]
            blueprint = library.find(target["blueprint_id"])
            actor = world.try_spawn_actor(blueprint, _point(carla, target["transform_m"]))
            if actor is None:
                raise ValueError("Native person/vehicle target spawn failed: " + role)
            actors["target_vehicle" if role == "vehicle" else "person"] = actor
            owned.append(actor)
        for role in ("ego", "oncoming"):
            if abs(_radius(actors[role]) - site["reviewed_body_radii_m"][role]) > .25:
                raise ValueError("Native vehicle body differs from source-reviewed radius: " + role)
        requested = _requested_lights(carla, case["requested_beam"])
        actors["ego"].set_light_state(requested)
        cameras = {}
        for view in VIEWS:
            camera = _sensor(carla, world, library, actors["ego"], camera_specs[view], view)
            owned.append(camera)
            cameras[view] = camera
        recorder = CameraRecorder(cameras, output)
        recorder.start()
        pipeline = PipelineCapture(client, actors["ego"], output, case["case_id"])
        states, maps, video_rows, roi_rows = [], [], [], []
        eye_offsets = site.get("driver_eye_offsets_m")
        if not isinstance(eye_offsets, dict) or set(eye_offsets) != {"ego", "oncoming"}:
            raise ValueError("source-reviewed driver-eye offsets required")
        speed_requests = site.get("speed_requests_mps")
        if not isinstance(speed_requests, dict) or set(speed_requests) != {"ego", "oncoming"}:
            raise ValueError("reviewed speed requests required")
        for index in range(ticks):
            for role in ("ego", "oncoming"):
                actor = actors[role]
                actor.apply_control(_route_control(carla, actor, site["routes"][role],
                                                   index, speed_requests[role]))
            frame = world.tick()
            snapshot_row = world.get_snapshot()
            if type(frame) is not int or snapshot_row.frame != frame:
                raise ValueError("Native world snapshot/frame mismatch")
            pipeline.capture(frame, snapshot_row.timestamp.elapsed_seconds)
            source_frames = recorder(frame)
            if any(source_frames[view] != frame for view in VIEWS):
                raise ValueError("original four-camera frame join differs")
            actor_rows = {}
            for role, actor in actors.items():
                actor_rows[role] = {"id": actor.id, "center_m": _center(actor)}
            for role in ("ego", "oncoming"):
                actor = actors[role]
                actor_rows[role].update({"speed_mps": actor.get_velocity().length(),
                                        "body_radius_m": _radius(actor),
                                        "driver_eye_m": _eye(actor, eye_offsets[role])})
            polygon = site["highway_or_shoulder_polygon_xy_m"]
            corners = actors["ego"].bounding_box.get_world_vertices(actors["ego"].get_transform())
            inside_count = sum(_inside(vertex.x, vertex.y, polygon) for vertex in corners)
            actor_rows["ego"].update({"lamp_command_bits": int(requested),
                                        "lamp_state_bits": int(actors["ego"].get_light_state()),
                                        "on_traveled_highway_or_adjacent_shoulder": inside_count == len(corners),
                                        "body_corner_inside_highway_count": inside_count})
            actor_rows["oncoming"]["opposing_route"] = True
            regions = {}
            for role, view in (("person", "approach"), ("target_vehicle", "approach")):
                actor = actors[role]
                vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
                matrix = cameras[view].get_transform().get_inverse_matrix()
                width, height = PROFILE_DIMENSIONS[view]
                regions[role] = bbox([[v.x, v.y, v.z] for v in vertices], matrix,
                                     width, height, camera_specs[view]["fov_deg"])
            if case["branch"] == "oncoming":
                view = "driver_reference"
                matrix = cameras[view].get_transform().get_inverse_matrix()
                width, height = PROFILE_DIMENSIONS[view]
                regions["oncoming_eye"] = bbox(eye_cube(actor_rows["oncoming"]["driver_eye_m"]),
                                                matrix, width, height,
                                                camera_specs[view]["fov_deg"])
            roi_rows.append({"frame": frame, "source_kind": "reviewed_original_projection",
                             "diagnostic_fixture": False,
                             "calibration_source_sha256": site["camera_calibration_sha256"],
                             "projection_source_sha256": site["projection_review_sha256"],
                             "regions": regions})
            states.append({"frame": frame, "time_s": snapshot_row.timestamp.elapsed_seconds,
                           "actors": actor_rows})
            maps.append({"frame": frame, **{view + "_source_frame": source_frames[view]
                                              for view in VIEWS}})
            video_rows.append({"video_frame": index, "carla_frame": frame,
                               "time_s": snapshot_row.timestamp.elapsed_seconds})
        media = recorder.finish(ticks)
        recorder = None
        output.mkdir(parents=True, exist_ok=True)
        (output / "site-packet.json").write_bytes(Path(packet_path).read_bytes())
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "source": "PipelineCapture original live run"}, sort_keys=True) + "\n")
        for name, rows in (("actor-state.jsonl", states), ("camera-frame-map.jsonl", maps),
                           ("video_frames.jsonl", video_rows), ("roi-frames.jsonl", roi_rows),
                           ):
            (output / name).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        movies = encode_original_videos(output, video_rows)
        hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")}
        pixel_hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                        for name in ("roi-frames.jsonl", "camera-frame-map.jsonl",
                                     "approach.zip", "driver_reference.zip")}
        receipt = {"format": "beam-road-native-source-v1", "case_id": case["case_id"],
                   "frame_count": ticks, "source_hashes": hashes,
                   "pixel_source_hashes": pixel_hashes,
                   "camera_archives": media, "camera_movies": movies,
                   "requested_beam": case["requested_beam"],
                   "physical_acceptance_claimed": False}
        (output / "native-source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        completed = True
        return receipt
    finally:
        try:
            try:
                if pipeline is not None:
                    pipeline.close(confirmed=completed)
            finally:
                if recorder is not None:
                    recorder.close()
                for actor in reversed(owned):
                    actor.destroy()
        finally:
            restore(client, saved)
