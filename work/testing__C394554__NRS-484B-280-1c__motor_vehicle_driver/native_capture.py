"""Original CARLA acquisition for a physical transit-stop pedestrian pair.

CARLA is imported only for a Native run. The scripted-driver event is retained
as an input source, never presented as evidence of human cognition.
"""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from road_scene import controller, footprint, load_site, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def vertices(actor):
    return [[point.x, point.y, point.z] for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def start_recorder(client, output):
    path = Path(output) / "carla_recorder.log"
    if path.exists():
        raise RuntimeError("original CARLA recorder output already exists")
    if client.start_recorder(str(path), True) is False:
        raise RuntimeError("original CARLA recorder failed to start")
    return path


def stop_recorder(client, path):
    client.stop_recorder()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("original CARLA recorder output missing or empty")


def inspect_road(world, carla, scene, output, bus, stop):
    mapping = world.get_map()
    road_samples = []
    start_x = round(scene["ego_start_xy_m"][0])
    end_x = round(scene["ego_end_xy_m"][0])
    if start_x >= end_x:
        raise ValueError("authored ego route direction changed")
    stations = list(range(start_x, end_x + 1, 5))
    if stations[-1] != end_x:
        stations.append(end_x)
    for x in stations:
        point = carla.Location(x=float(x), y=scene["ego_start_xy_m"][1], z=0.0)
        waypoint = mapping.get_waypoint(point)
        if waypoint is None or math.hypot(waypoint.transform.location.x - x,
                                         waypoint.transform.location.y - point.y) > min(2.5, waypoint.lane_width / 2 + 0.3):
            raise ValueError("authored ego route absent from original Native road")
        road_samples.append(waypoint)
    if len({(item.road_id, item.lane_id) for item in road_samples}) != 1:
        raise ValueError("ego route not on one original driving lane")
    if any(abs(((item.transform.rotation.yaw + 180) % 360) - 180) > 30
           for item in road_samples):
        raise ValueError("original driving lane points away from authored ego approach")
    width = min(item.lane_width for item in road_samples)
    if not math.isfinite(width) or width < 3:
        raise ValueError("original road width cannot support authored approach")
    bus_body = vertices(bus)
    bx0, by0, bx1, by1 = footprint(bus_body)
    stop_position = stop.get_transform().location
    bus_position = bus.get_transform().location
    # This is an engineering boarding-side proxy derived from original bus body.
    # Actual door side and visually complete boarding still need local review.
    door_region = {"x_min": bx0, "x_max": bx1,
                   "y_min": by1 - 0.5, "y_max": by1}
    source = output / "map.xodr"
    source.write_text(mapping.to_opendrive())
    site = {"format": "worker-transit-stop-site", "cell_id": "C394554",
            "layout": "road", "control": "bus_stop",
            "map_source": {"path": "map.xodr", "sha256": sha(source)},
            "road": {"road_id": road_samples[0].road_id,
                     "lane_source": "original Native driving-lane waypoint and OpenDRIVE"},
            "stop": {"actor_id": stop.id, "blueprint_id": stop.type_id,
                     "position_m": [stop_position.x, stop_position.y, stop_position.z],
                     "position_source": "original Native stop-prop transform"},
            "bus": {"actor_id": bus.id, "blueprint_id": bus.type_id,
                    "position_m": [bus_position.x, bus_position.y, bus_position.z],
                    "body_vertices_m": bus_body,
                    "door_side_source": "curb-facing side of original bus body; local pixel review required",
                    "door_region_source": "engineering proxy from original bus body; actual door placement unverified",
                    "door_region_m": door_region},
            "ego_start_xy_m": scene["ego_start_xy_m"],
            "ego_lane_start_position_m": [road_samples[0].transform.location.x,
                                          road_samples[0].transform.location.y,
                                          road_samples[0].transform.location.z],
            "ego_end_xy_m": scene["ego_end_xy_m"],
            "pedestrian_start_xy_m": scene["pedestrian_start_xy_m"],
            "pedestrian_end_xy_m": scene["pedestrian_end_xy_m"],
            "sample_lane_ids": [item.lane_id for item in road_samples],
            "sample_lane_widths_m": [item.lane_width for item in road_samples]}
    write(output / "transit-site.json", site)
    load_site(output / "transit-site.json")
    return site


class Cameras:
    SPECS = (("overview", 1920, 1080, (0, 0, 45, -90)),
             ("approach", 1280, 720, (-15, -12, 12, -25)),
             ("reference_corner", 1280, 720, (4, 4, 12, -45)),
             ("driver_reference", 1280, 720, (0, 0, 2, 0)))

    @staticmethod
    def transform(name, pose, site, carla):
        x, y, z, pitch = pose
        if name in ("approach", "reference_corner"):
            stop = site["stop"]["position_m"]
            bus = site["bus"]["position_m"]
            target = ((stop[0] + bus[0]) / 2, (stop[1] + bus[1]) / 2, 1.5)
            dx, dy = target[0] - x, target[1] - y
            if math.hypot(dx, dy) < 1:
                raise ValueError("transit encounter camera is too close to target")
            yaw = math.degrees(math.atan2(dy, dx))
            pitch = math.degrees(math.atan2(target[2] - z, math.hypot(dx, dy)))
        else:
            yaw = 0
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(pitch=pitch, yaw=yaw))

    def __init__(self, world, ego, output, carla, site):
        self.sensors, self.encoders, self.queues = [], {}, {}
        try:
            for name, width, height, pose in self.SPECS:
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                transform = self.transform(name, pose, site, carla)
                sensor = world.spawn_actor(blueprint, transform,
                                           attach_to=ego if name == "driver_reference" else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                sensor.listen(lambda image, q=frames: q.put_nowait(image))
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
                           "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
                           "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                        stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        for name, _, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame differs from original world frame: " + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                errors.append(repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    errors.append("camera encoder failed: " + name)
            except BaseException as error:
                errors.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        if errors:
            raise RuntimeError("; ".join(errors))


def run_native(scene, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields, equal

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError("Native attempt directory must already exist")
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    actors, cameras, capture, frame_map = [], None, None, None
    phase, errors, count, restored, recorder_started = "initializing", [], 0, False, False
    try:
        library = world.get_blueprint_library()
        vehicles = [item for item in library.filter(scene["ego_blueprint_filter"])
                    if "bus" not in item.id.lower() and "fusorosa" not in item.id.lower()]
        walkers = list(library.filter(scene["pedestrian_blueprint_filter"]))
        buses = list(library.filter(scene["bus_blueprint_filter"]))
        stops = [item for item in library.filter(scene["stop_blueprint_filter"])
                 if "busstop" in item.id.lower() or "bus_stop" in item.id.lower()]
        if not vehicles or not walkers or not buses or not stops:
            raise ValueError("original Native vehicle, bus, stop or pedestrian blueprint unavailable")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)

        def spawn_at(point, yaw=0, align_driving=False):
            waypoint = world.get_map().get_waypoint(carla.Location(x=point[0], y=point[1], z=0))
            z = waypoint.transform.location.z + .5 if waypoint else .5
            if align_driving:
                if waypoint is None or math.hypot(waypoint.transform.location.x - point[0],
                                                  waypoint.transform.location.y - point[1]) > min(
                                                      2.5, waypoint.lane_width / 2 + 0.3):
                    raise ValueError("ego spawn lacks original nearby driving lane")
                if abs(((waypoint.transform.rotation.yaw + 180) % 360) - 180) > 30:
                    raise ValueError("ego spawn lane points away from authored approach")
                return carla.Transform(carla.Location(x=waypoint.transform.location.x,
                                                      y=waypoint.transform.location.y,z=z),
                                       carla.Rotation(yaw=waypoint.transform.rotation.yaw))
            return carla.Transform(carla.Location(x=point[0], y=point[1], z=z), carla.Rotation(yaw=yaw))

        ego = world.spawn_actor(vehicles[0], spawn_at(scene["ego_start_xy_m"], align_driving=True))
        actors.append(ego)
        bus = world.spawn_actor(buses[0], spawn_at(scene["bus_xy_m"]))
        actors.append(bus)
        stop = world.spawn_actor(stops[0], spawn_at(scene["bus_stop_xy_m"]))
        actors.append(stop)
        pedestrian = world.spawn_actor(walkers[0], spawn_at(scene["pedestrian_start_xy_m"], 90))
        actors.append(pedestrian)
        if any(actor is None for actor in (ego, bus, stop, pedestrian)) or len(
                {actor.id for actor in (ego, bus, stop, pedestrian)}) != 4:
            raise ValueError("original motorist, bus, stop and pedestrian identities not distinct")
        bus.set_simulate_physics(False)
        site = inspect_road(world, carla, scene, output, bus, stop)
        cameras = Cameras(world, ego, output, carla, site)
        capture = PipelineCapture(client, ego, output, scene["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        collision_events = []
        collision = world.spawn_actor(library.find("sensor.other.collision"), carla.Transform(), attach_to=ego)
        actors.append(collision)
        collision.listen(lambda event: collision_events.append((event.frame, event.other_actor.id)))
        recorder_path = start_recorder(client, output)
        recorder_started = True
        phase = "capturing"
        with (output / "encounter-history.jsonl").open("x", buffering=1) as stream:
            for index in range(round(scene["duration_s"] * scene["rate_hz"])):
                ego_body, ped_body = vertices(ego), vertices(pedestrian)
                approach_gap = max(0.0, min(v[0] for v in ped_body) - max(v[0] for v in ego_body))
                event = ({"source": "original_driver_input", "observed": True,
                          "kind": "scripted_observation_trigger", "input_gap_m": approach_gap}
                         if approach_gap <= scene["instrumented_observation_distance_m"] else None)
                sample = {"ego_body_vertices_m": ego_body, "pedestrian_body_vertices_m": ped_body,
                          "bus_body_vertices_m": vertices(bus),
                          "bus_actor_id": bus.id, "stop_actor_id": stop.id,
                          "ego_speed_mps": speed(ego), "ego_brake": 0.0,
                          "ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
                          "ego_class_source": ego.type_id,
                          "pedestrian_class_source": pedestrian.type_id,
                          "driver_control_source": "scripted-driver-controller",
                          "driver_observation_event": event,
                          "passenger_phase": scene["passenger_phase"]}
                measured = measure(site, sample)
                command = controller(measured)
                ego.apply_control(carla.VehicleControl(throttle=command["throttle"],
                                                       brake=command["brake"], steer=command["steer"]))
                fraction = (min(1.0, (index + 1) * scene["pedestrian_target_speed_mps"]
                                / scene["rate_hz"] / 2.0)
                            if scene["passenger_phase"] == "boarding_bus" else 0.0)
                start, end = scene["pedestrian_start_xy_m"], scene["pedestrian_end_xy_m"]
                destination = [start[axis] + fraction * (end[axis] - start[axis]) for axis in (0, 1)]
                pedestrian.set_transform(spawn_at(destination, 90))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise RuntimeError("original world frame identity changed")
                time_s = snapshot.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                sample.update(ego_body_vertices_m=vertices(ego),
                              pedestrian_body_vertices_m=vertices(pedestrian),
                              bus_body_vertices_m=vertices(bus),
                              ego_speed_mps=speed(ego), ego_brake=command["brake"])
                value = measure(site, sample)
                row = {"frame": frame, "time_s": time_s, **sample,
                       "pedestrian_stop_distance_m": value["pedestrian_stop_distance_m"],
                       "pedestrian_bus_door_region_gap_m": value["pedestrian_bus_door_region_gap_m"],
                       "contact_event": (frame, pedestrian.id) in collision_events,
                       "control_command": command}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                count += 1
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        stop_recorder(client, recorder_path); recorder_started = False
        names = ["trace.jsonl", "video_frames.jsonl", "encounter-history.jsonl", "transit-site.json",
                 "map.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, *_ in Cameras.SPECS]]
        write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(output / name)}
                                             for name in names})
        phase = "sealed"
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        if recorder_started:
            try:
                client.stop_recorder()
            except BaseException as error:
                errors.append(repr(error))
        for resource in (capture, frame_map, cameras):
            if resource:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        for actor in reversed(actors):
            if actor:
                try:
                    actor.destroy()
                except BaseException as error:
                    errors.append(repr(error))
        try:
            world.apply_settings(original)
            restored = all(equal(fields(world.get_settings()).get(key), value)
                           for key, value in fields(original).items())
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=count,
                         restoration={"restored": True,
                                      "settings_readback": "synchronous mode and fixed delta restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, *_ in Cameras.SPECS},
                         context={"transit_stop": site})
        else:
            write(output / "native-run-status.json",
                  {"phase": phase, "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
