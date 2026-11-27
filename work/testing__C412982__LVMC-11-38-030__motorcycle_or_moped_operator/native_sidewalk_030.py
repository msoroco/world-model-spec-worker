"""Original Native City sidewalk device route, operator conduct and video acquisition."""

from __future__ import annotations

from hashlib import sha256
import json
from math import atan2, degrees, hypot
from pathlib import Path
import shutil

from camera_capture import Cameras
from sidewalk_030 import construct, inside, measure_original, need


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


class Adapter:
    def __init__(self, world, carla, site):
        self.world, self.carla, self.site = world, carla, site
        self.owned = []
        self.route = None
        self.walker = None

    def spawn_device(self, xy, blueprint_id):
        c = self.carla
        bp = self.world.get_blueprint_library().find(blueprint_id)
        need(bp.id == blueprint_id, "reviewed Native cycle or scooter asset absent")
        z = self.site.get("spawn_height_m")
        need(type(z) in (int, float), "original surveyed device spawn height missing")
        route = self.site["ego_route_xy"]
        yaw = degrees(atan2(route[1][1] - route[0][1],
                            route[1][0] - route[0][0]))
        actor = self.world.try_spawn_actor(
            bp, c.Transform(c.Location(x=xy[0], y=xy[1], z=z), c.Rotation(yaw=yaw)))
        need(actor is not None and actor.is_alive and actor.type_id == blueprint_id,
             "original device spawn/readback failed")
        self.owned.append(actor)
        return actor

    def set_route(self, device, route):
        need(device in self.owned and len(route) >= 2, "original route actor missing")
        self.route = tuple(tuple(x) for x in route)

    def set_conduct(self, device, conduct, operator_id):
        need(device in self.owned and operator_id, "original operator identity missing")
        self.conduct = conduct
        if conduct == "walking":
            bp_id = self.site["operator_conduct"]["walker_blueprint_id"]
            bp = self.world.get_blueprint_library().find(bp_id)
            need(bp.id == bp_id, "reviewed pedestrian walker asset absent")
            first = self.route[0]
            c = self.carla
            walker = self.world.try_spawn_actor(bp, c.Transform(
                c.Location(x=first[0], y=first[1] + .75,
                           z=self.site["spawn_height_m"])))
            need(walker is not None and walker.is_alive and walker.type_id == bp_id,
                 "original walking operator spawn/readback failed")
            self.owned.append(walker)
            self.walker = walker

    def set_site(self, device, sidewalks, road, municipality):
        need(device in self.owned and sidewalks and road and municipality,
             "original physical site boundaries missing")
        self.surfaces = (sidewalks, road, municipality)

    def control(self, device, route_index):
        location = device.get_location()
        target = self.route[route_index]
        dx, dy = target[0] - location.x, target[1] - location.y
        distance = hypot(dx, dy)
        speed = 1.2 if self.conduct == "walking" else 3.0
        if distance < 1.2 and route_index == len(self.route) - 1:
            speed = 0.0
        if distance > .01:
            device.set_target_velocity(self.carla.Vector3D(
                x=speed * dx / distance, y=speed * dy / distance, z=0))
        if self.walker is not None:
            walker_location = self.walker.get_location()
            wx = location.x - walker_location.x
            wy = location.y + .75 - walker_location.y
            gap = hypot(wx, wy)
            direction = self.carla.Vector3D(x=wx / gap if gap else 0,
                                             y=wy / gap if gap else 0, z=0)
            self.walker.apply_control(self.carla.WalkerControl(
                direction=direction, speed=min(1.4, max(0, gap))))
        return {"target_xy": list(target), "requested_speed_mps": speed,
                "conduct": self.conduct}


def run_native(cfg, case, site, site_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    need(output.is_dir(), "Native attempt directory must exist")
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    adapter = cameras = capture = frame_map = None
    errors, rows, phase, restored = [], [], "initializing", False
    try:
        map_object = world.get_map()
        need(map_object.name == site["map_name"] and
             sha256(map_object.to_opendrive().encode()).hexdigest() ==
             site["map_opendrive_sha256"],
             "reviewed City sidewalk original map differs from Native world")
        archive = output / "reviewed-city-sidewalk-packet"
        archive.mkdir(exist_ok=False)
        shutil.copy2(site_path, archive / "site.json")
        for item in site["sources"].values():
            source = (Path(site_path).parent / item["path"]).resolve()
            target = archive / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        adapter = Adapter(world, carla, site)
        device = construct(adapter, site, case)["device"]
        write(output / "acquisition-provenance.json",
              {"provenance_kind": "native", "diagnostic_fixture": False,
               "original_site_sha256": sha(site_path)})
        cameras = Cameras(world, carla, device, adapter.route[-1], output)
        capture = PipelineCapture(client, device, output, cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        phase = "capturing"
        route_index = 1
        with (output / "city-sidewalk-history.jsonl").open("x", buffering=1) as stream:
            for _ in range(round(cfg["duration_s"] * cfg["rate_hz"])):
                position = device.get_location()
                while (route_index < len(adapter.route) - 1 and
                       hypot(position.x - adapter.route[route_index][0],
                             position.y - adapter.route[route_index][1]) <= 1.5):
                    route_index += 1
                command = adapter.control(device, route_index)
                frame = world.tick()
                tick = world.get_snapshot()
                need(frame == tick.frame, "original Native frame identity changed")
                time_s = tick.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                p = device.get_location()
                row = {"original_frame": frame, "time_s": time_s,
                       "position_xy": [p.x, p.y],
                       "device_actor_id": device.id,
                       "device_id": site["device"]["device_id"],
                       "operator_id": site["operator_conduct"]["operator_id"],
                       "operator_actor_id": adapter.walker.id if adapter.walker else device.id,
                       "device_source_sha256": site["device_specification_source_sha256"],
                       "operator_source_sha256": site["operator_conduct_source_sha256"],
                       "requested_control": command,
                       "original_device_speed_mps": hypot(device.get_velocity().x,
                                                              device.get_velocity().y),
                       "mounted_riding_source": site["operator_conduct"]["kind"] == "riding",
                       "municipality_source_sha256": site["municipal_boundary_source_sha256"],
                       "on_selected_sidewalk": inside([p.x, p.y],
                           site["sidewalk_polygons_xy"][case.side])}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close()
        capture = None
        frame_map.close()
        frame_map = None
        cameras.close()
        cameras = None
        write(output / "city-sidewalk-site.json", site)
        write(output / "city-sidewalk-measurement-preview.json",
              measure_original(rows, site, case))
        names = ["trace.jsonl", "video_frames.jsonl", "city-sidewalk-history.jsonl",
                 "city-sidewalk-site.json", "road.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, _, _ in Cameras.SPECS]]
        names.extend(str(p.relative_to(output)) for p in archive.rglob("*") if p.is_file())
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
            restored = restore(client, saved)["restored"]
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={"restored": True,
                                      "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={"city_sidewalk_case": cfg["selected_case_id"]})
        else:
            write(output / "native-run-status.json",
                  {"phase": phase, "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
