"""Native capture for source-identified intersection and street-corner reverse routes.

This entrypoint is CARLA-lazy. It retains original geometry, control and video
joins for the independent saved-source analyzer; no physical outcome is assumed.
"""

import argparse
import hashlib
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from reverse_alternative_route import ReverseRouteController, review_route
from reverse_control import reverse_vehicle


ASSIGNMENT = "testing__C215286__NRS-484B-113-2__motor_vehicle_driver"
CASES = {
    ASSIGNMENT + "__reverse_into_intersection": ("intersection", True),
    ASSIGNMENT + "__reverse_stops_before_intersection": ("intersection", False),
    ASSIGNMENT + "__reverse_around_street_corner": ("street_corner", True),
    ASSIGNMENT + "__reverse_stops_before_street_corner": ("street_corner", False),
}


def _site_name(alternative, expected_entry):
    return alternative + ("_site.json" if expected_entry else "_stop_site.json")


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if len(points) < 4 or any(not all(math.isfinite(value) for value in point)
                              for point in points):
        raise ValueError("Incomplete Native vehicle body")
    return points


def _center(points):
    return [(min(point[axis] for point in points) +
             max(point[axis] for point in points)) / 2 for axis in (0, 1)]


def _sensor_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Original camera frame missing") from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError("Original camera skipped Native frame")
    raise ValueError("Original camera frame join failed")


def _load_site(root, case_id):
    if case_id not in CASES:
        raise ValueError("Unknown exact backing alternative case")
    alternative, expected_entry = CASES[case_id]
    name = _site_name(alternative, expected_entry)
    path = root / name
    if not path.is_file():
        path = root / "site_templates" / name
    site = json.loads(path.read_text())
    if site.get("alternative") != alternative or site.get("expected_entry") is not expected_entry:
        raise ValueError("Alternative site identity differs")
    for key in ("native_map_id", "road_id", "geometry_source", "camera_source",
                "route_xy_m", "start_transform", "start_body_vertices_xy_m",
                "region_polygon_xy_m", "vehicle_blueprint_id"):
        if not site.get(key):
            raise ValueError("Incomplete alternative site: " + key)
    if alternative == "street_corner" and not site.get("road_topology_source"):
        raise ValueError("Street-corner topology source missing")
    for key in ("geometry_source", "camera_source") + (("road_topology_source",)
                                                        if alternative == "street_corner" else ()):
        ref = site[key]
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            raise ValueError("Missing original source binding: " + key)
        rel = Path(ref["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe original source path")
        source = root / rel
        if not source.is_file():
            source = root / "site_templates" / rel
        if hashlib.sha256(source.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("Changed original site source: " + key)
    review = review_route(site["route_xy_m"], site["start_body_vertices_xy_m"],
                          site["region_polygon_xy_m"], alternative=alternative,
                          expected_entry=expected_entry)
    return site, review


def _require_native_review(site):
    if (site.get("site_review_status") != "reviewed_native_site"
            or not site.get("site_reviewer")
            or not site.get("site_review_basis")
            or not site.get("camera_review_basis")):
        raise ValueError("Original Native site and camera review required before capture")


def _publish_site_sources(output, site, case_id):
    """Copy reviewed bundled templates into the original capture namespace."""
    alternative, expected_entry = CASES[case_id]
    names = [_site_name(alternative, expected_entry)]
    for key in ("geometry_source", "camera_source", "road_topology_source"):
        ref = site.get(key)
        if ref:
            names.append(ref["path"])
    for name in names:
        target = output / name
        template = output / "site_templates" / name
        if not template.is_file():
            if not target.is_file():
                raise ValueError("Missing reviewed site template: " + name)
            continue
        if target.is_file():
            if target.read_bytes() != template.read_bytes():
                raise ValueError("Original site differs from reviewed template: " + name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(template.read_bytes())


def _cameras(carla, site):
    points = site["region_polygon_xy_m"]
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    start = site["start_transform"]

    def pose(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))

    return {
        "overview": pose(cx, cy, start["z"] + 35, start["yaw_deg"], -75),
        "approach": pose(start["x"] + 10, start["y"], start["z"] + 6,
                         start["yaw_deg"] + 180, -15),
        "reference_corner": pose(cx + 8, cy + 8, start["z"] + 8,
                                 start["yaw_deg"] - 135, -30),
        "driver_reference": pose(1, 0, 1.65, 180, -5),
    }


def _record_alternative(actor, snapshot, site):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    yaw = float(transform.rotation.yaw)
    body = _body(actor)
    return {"frame": int(snapshot.frame),
            "time_s": float(snapshot.timestamp.elapsed_seconds),
            "road_id": site["road_id"],
            "native_reverse": bool(actor.get_control().reverse),
            "ego_forward_xy": [math.cos(math.radians(yaw)),
                               math.sin(math.radians(yaw))],
            "ego_body_vertices_xy_m": body,
            "body_vertices_m": body,
            "heading_deg": yaw,
            "velocity_mps": [float(velocity.x), float(velocity.y)],
            "actor_id": int(actor.id)}


def capture(output, host, port, case_id):
    output = Path(output).resolve()
    if not (output / "construction.json").is_file():
        raise ValueError("Materialized exact construction required")
    site, review = _load_site(output, case_id)
    _require_native_review(site)
    _publish_site_sources(output, site, case_id)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot as snapshot_world

    config = json.loads((output / "config.json").read_text())
    if config.get("selected_case_id") != case_id or config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("Exact 20 Hz, 45-second alternative construction required")
    if [camera.get("name") for camera in config.get("cameras", [])] != list(PROFILE):
        raise ValueError("Four ordered original cameras required")
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot_world(client)
    world = client.get_world()
    actor = None
    helper = None
    encoders = {}
    frames = 0
    error = None
    try:
        native_map = world.get_map()
        if native_map.name != site["native_map_id"]:
            raise ValueError("Native map differs from alternative site")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        start = site["start_transform"]
        location = carla.Location(x=start["x"], y=start["y"], z=start["z"])
        waypoint = native_map.get_waypoint(location, project_to_road=False)
        if waypoint is None or waypoint.road_id != site["road_id"]:
            raise ValueError("Reverse start is not on sourced road")
        blueprint = world.get_blueprint_library().find(site["vehicle_blueprint_id"])
        actor = world.try_spawn_actor(blueprint, carla.Transform(
            location, carla.Rotation(yaw=start["yaw_deg"])))
        if actor is None:
            raise ValueError("Native reverse vehicle spawn failed")
        actual = review_route(site["route_xy_m"], _body(actor),
                              site["region_polygon_xy_m"],
                              alternative=site["alternative"],
                              expected_entry=site["expected_entry"])
        context = {
            "alternative": site["alternative"],
            "expected_entry": site["expected_entry"],
            "native_map_id": site["native_map_id"],
            "road_id": site["road_id"],
            "site_packet_source": {
                "path": _site_name(site["alternative"], site["expected_entry"]),
                "sha256": hashlib.sha256((output / _site_name(
                    site["alternative"], site["expected_entry"])).read_bytes()).hexdigest(),
            },
            "geometry_source": site["geometry_source"],
            "camera_source": site["camera_source"],
            "road_topology_source": site.get("road_topology_source"),
            "planned_route_review": review,
            "native_body_route_review": actual,
            "intersection_polygon_xy_m": site["region_polygon_xy_m"]
            if site["alternative"] == "intersection" else None,
            "street_corner_region_xy_m": site["region_polygon_xy_m"]
            if site["alternative"] == "street_corner" else None,
        }
        (output / "reverse_site_context.json").write_text(json.dumps(context, indent=2) + "\n")
        controller = ReverseRouteController(site["route_xy_m"])
        with reverse_vehicle(world, actor, carla.VehicleControl, throttle=.1):
            with source_cameras(world, actor, _cameras(carla, site), config["cameras"]) as sensors:
                queues = {name: Queue() for name in PROFILE}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    for name, (width, height) in PROFILE.items():
                        encoders[name] = stack.enter_context(
                            FFV1Writer(output / (name + ".mkv"), width, height))
                    mapping = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                    history = stack.enter_context((output / "reverse_history.jsonl").open("x", buffering=1))
                    helper = PipelineCapture(client, actor, output, case_id,
                                             required_observations=config["required_atoms"])
                    try:
                        for _ in range(900):
                            velocity = actor.get_velocity()
                            command = controller.step(
                                _center(_body(actor)), actor.get_transform().rotation.yaw,
                                math.hypot(float(velocity.x), float(velocity.y)))
                            actor.apply_control(carla.VehicleControl(
                                throttle=command["throttle"], brake=command["brake"],
                                steer=command["steer"], reverse=True))
                            world.tick()
                            snapshot = world.get_snapshot()
                            for name in PROFILE:
                                image = _sensor_frame(queues[name], snapshot.frame)
                                encoders[name].write(bytes(image.raw_data))
                            helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                            mapping.append(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                            history.write(json.dumps(_record_alternative(actor, snapshot, site), separators=(",", ":")) + "\n")
                            frames += 1
                    finally:
                        helper.close()
                        helper = None
    except BaseException as caught:
        error = caught
        raise
    finally:
        cleanup = []
        if helper is not None:
            try:
                helper.close(confirmed=False)
            except BaseException as caught:
                cleanup.append(str(caught))
        if actor is not None:
            try:
                actor.destroy()
            except BaseException as caught:
                cleanup.append(str(caught))
        restoration = restore(client, saved)
        if error is None and not cleanup:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: encoder.exit_code
                                             for name, encoder in encoders.items()},
                         context={"alternative_route_review": review,
                                  "physical_acceptance_claimed": False})
        if error is None and cleanup:
            raise ValueError("Native cleanup failed: " + "; ".join(cleanup))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = json.loads(Path(__file__).with_name("config.json").read_text())["selected_case_id"]
    if args.check:
        site, review = _load_site(Path(__file__).parent, case_id)
        print(json.dumps({"case_id": case_id, "alternative": site["alternative"],
                          "route_review": review, "simulation_started": False}))
    else:
        if not args.output_dir:
            raise ValueError("--output-dir required for Native capture")
        capture(args.output_dir, args.host, args.port, case_id)


if __name__ == "__main__":
    main()
