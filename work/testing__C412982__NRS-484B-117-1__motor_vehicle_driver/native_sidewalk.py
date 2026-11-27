"""Original CARLA motion, body footprint and four-view sidewalk acquisition."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from camera_capture import Cameras
from sidewalk_case import BY_SUFFIX, construct
from sidewalk_measure import measure_frame


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def body_hull(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted(set((v.x, v.y) for v in vertices))

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower, upper = [], []
    for point in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return [list(point) for point in lower[:-1] + upper[:-1]]


def speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def steer_to(actor, xy):
    pose = actor.get_transform()
    desired = math.degrees(math.atan2(xy[1] - pose.location.y,
                                      xy[0] - pose.location.x))
    error = ((desired - pose.rotation.yaw + 180) % 360) - 180
    return max(-1.0, min(1.0, error / 35.0))


class Adapter:
    def __init__(self, world, carla):
        self.world, self.carla = world, carla
        self.owned = []
        self.route = None
        self.target = None
        self.target_region = None
        self.controller = None

    def spawn_vehicle(self, xy, blueprint_id):
        location = self.carla.Location(x=xy[0], y=xy[1], z=0)
        waypoint = self.world.get_map().get_waypoint(location, project_to_road=False)
        if waypoint is None:
            raise ValueError("reviewed road approach waypoint absent")
        location.z = waypoint.transform.location.z + .5
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(
            blueprint, self.carla.Transform(location, waypoint.transform.rotation))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError("reviewed motor vehicle spawn failed Native readback")
        self.owned.append(actor)
        return actor

    def set_route(self, ego, route):
        if ego not in self.owned or len(route) < 2:
            raise ValueError("reviewed sidewalk route absent")
        self.route = tuple(tuple(point) for point in route)
        self.target = tuple(self.route[-1])

    def set_target_region(self, ego, sidewalk, entrances, region, kind):
        if ego not in self.owned:
            raise ValueError("ego not owned")
        self.target_region = (sidewalk, entrances, region, kind)

    def enable_controller(self, ego, controller):
        if ego not in self.owned or controller != "route_follow_20hz":
            raise ValueError("unsupported sidewalk controller")
        self.controller = controller


def run_native(cfg, site, site_path, output, host, port):
    """Run one original 20 Hz episode; no fixture path can enter this method."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("Native attempt directory must already exist")
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    adapter = None
    cameras = capture = frame_map = None
    phase, errors, restored, rows = "initializing", [], False, []
    try:
        archive = output / "reviewed-site-packet"
        archive.mkdir(exist_ok=False)
        shutil.copy2(site_path, archive / "site.json")
        for item in site["sources"].values():
            source = (Path(site_path).parent / item["path"]).resolve()
            target = archive / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        map_source = Path(site_path).parent / site["sources"]["map"]["path"]
        map_record = json.loads(map_source.read_text(encoding="utf-8"))
        if (world.get_map().name != site["map_id"] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() !=
                map_record.get("opendrive_sha256")):
            raise ValueError("reviewed sidewalk map differs from Native world")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        adapter = Adapter(world, carla)
        case = BY_SUFFIX[cfg["selected_case_id"].split("__")[-1]]
        built = construct(adapter, site, case)
        ego = built["ego"]
        write(output / "acquisition-provenance.json",
              {"provenance_kind": "native", "diagnostic_fixture": False,
               "method": "original CARLA live run"})
        cameras = Cameras(world, carla, ego, adapter.target, output)
        capture = PipelineCapture(client, ego, output, cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        phase = "capturing"
        route_index = 1
        with (output / "sidewalk-history.jsonl").open("x", buffering=1) as stream:
            for _ in range(round(cfg["duration_s"] * cfg["rate_hz"])):
                position = ego.get_location()
                while (route_index < len(adapter.route) - 1 and
                       math.dist((position.x, position.y), adapter.route[route_index]) <= 2):
                    route_index += 1
                waypoint = adapter.route[route_index]
                distance = math.dist((position.x, position.y), waypoint)
                at_end = route_index == len(adapter.route) - 1 and distance <= 1.5
                control = {"throttle": 0.0 if at_end or speed(ego) >= 5 else .28,
                           "brake": .8 if at_end else 0.0,
                           "steer": 0.0 if at_end else steer_to(ego, waypoint),
                           "hand_brake": False}
                ego.apply_control(carla.VehicleControl(**control))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("original Native frame identity changed")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                row = {"original_frame": frame, "time_s": time_s,
                       "vehicle_actor_id": ego.id,
                       "body_polygon_xy": body_hull(ego),
                       "body_geometry_source_sha256": site["body_geometry_source_sha256"],
                       "position_m": [ego.get_location().x, ego.get_location().y,
                                      ego.get_location().z],
                       "ego_speed_mps": speed(ego),
                       "control_command": control,
                       "operator_context_source_sha256":
                           site["operator_identity_source_sha256"]}
                measured = measure_frame(row, site)
                row.update(measured)
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close()
        capture = None
        frame_map.close()
        frame_map = None
        cameras.close()
        cameras = None
        write(output / "sidewalk-site.json", site)
        names = ["trace.jsonl", "video_frames.jsonl", "sidewalk-history.jsonl",
                 "sidewalk-site.json", "road.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, _, _ in Cameras.SPECS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob("*") if path.is_file())
        write(output / "acquisition.json",
              {name: {"kind": "original_native", "sha256": sha(output / name)}
               for name in names})
        phase = "sealed"
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (capture, frame_map, cameras):
            if resource:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        if adapter:
            for actor in reversed(adapter.owned):
                try:
                    actor.destroy()
                except BaseException as error:
                    errors.append(repr(error))
        try:
            restored = restore(client, saved_world)["restored"]
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={"restored": True,
                                      "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={"sidewalk_case": cfg["selected_case_id"]})
        else:
            write(output / "native-run-status.json",
                  {"phase": phase, "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
