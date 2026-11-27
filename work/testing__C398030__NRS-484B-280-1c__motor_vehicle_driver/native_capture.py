"""Original CARLA acquisition for the road-without-sidewalk pedestrian pair.

CARLA is imported only for a Native run. The scripted-driver event is retained
as an input source, never presented as evidence of human cognition.
"""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from road_scene import controller, observed_encounter


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def vertices(actor):
    return [[point.x, point.y, point.z] for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def inspect_school(world, carla, scene, output):
    """Acquire two original school signs and place the route between them.

    The pair is a construction witness only. Independent local review still
    must verify official designation and camera readability.
    """
    mapping = world.get_map()
    source = output / "map.xodr"
    source.write_text(mapping.to_opendrive())
    signs = list(world.get_environment_objects(carla.CityObjectLabel.TrafficSigns))
    school = [item for item in signs if "school" in str(getattr(item, "name", "")).lower()]
    pairs = []
    for left in school:
        for right in school:
            p, q = left.bounding_box.location, right.bounding_box.location
            if not (20 <= q.x - p.x <= 100 and abs(q.y - p.y) <= 20):
                continue
            midpoint = carla.Location(x=(p.x + q.x) / 2, y=(p.y + q.y) / 2, z=0)
            lane = mapping.get_waypoint(midpoint)
            if lane is None or lane.lane_type != carla.LaneType.Driving:
                continue
            yaw = (lane.transform.rotation.yaw + 360) % 360
            if min(yaw, 360 - yaw) > 10:
                continue
            if not math.isfinite(lane.lane_width) or lane.lane_width < 3:
                continue
            pairs.append((left, right, lane))
    if not pairs:
        raise ValueError("original Native school boundary signs and aligned driving lane absent")
    left, right, lane = min(pairs, key=lambda row: row[1].bounding_box.location.x - row[0].bounding_box.location.x)
    x0, x1 = left.bounding_box.location.x, right.bounding_box.location.x
    y = lane.transform.location.y
    scene["ego_start_xy_m"] = [x0 - scene["ego_spawn_offset_m"], y]
    scene["ego_end_xy_m"] = [x1 + 20, y]
    scene["pedestrian_start_xy_m"] = [(x0 + x1) / 2, y + lane.lane_width / 2 + 1.5]
    scene["pedestrian_end_xy_m"] = list(scene["pedestrian_start_xy_m"])
    markers = [{"original_object_id": str(item.id), "name": str(item.name),
                "location_xy_m": [item.bounding_box.location.x, item.bounding_box.location.y]}
               for item in (left, right)]
    site = {"format": "worker-school-setting-site", "cell_id": "C398030",
            "layout": "school_zone", "control": "school",
            "crossing_type": "school_zone", "school_designation_source": "original Native school traffic-sign objects",
            "map_source": {"path": "map.xodr", "sha256": sha(source)},
            "school_boundary_markers": markers,
            "original_road_id": lane.road_id, "original_lane_id": lane.lane_id,
            "original_lane_width_m": lane.lane_width,
            "ego_start_xy_m": scene["ego_start_xy_m"], "ego_end_xy_m": scene["ego_end_xy_m"],
            "pedestrian_start_xy_m": scene["pedestrian_start_xy_m"],
            "pedestrian_end_xy_m": scene["pedestrian_end_xy_m"]}
    from road_scene import load_site
    write(output / "school-site.json", site)
    load_site(output / "school-site.json")
    return site


class Cameras:
    SPECS = (("overview", 1920, 1080, (0, 0, 45, -90)),
             ("approach", 1280, 720, (-15, -12, 12, -25)),
             ("reference_corner", 1280, 720, (4, 4, 12, -45)),
             ("driver_reference", 1280, 720, (0, 0, 2, 0)))

    def __init__(self, world, ego, output, carla):
        self.sensors, self.encoders, self.queues = [], {}, {}
        try:
            for name, width, height, pose in self.SPECS:
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                x, y, z, pitch = pose
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch))
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
    phase, errors, count, restored = "initializing", [], 0, False
    try:
        site = inspect_school(world, carla, scene, output)
        library = world.get_blueprint_library()
        vehicles = list(library.filter(scene["ego_blueprint_filter"]))
        walkers = list(library.filter(scene["pedestrian_blueprint_filter"]))
        if not vehicles or not walkers:
            raise ValueError("original Native vehicle or pedestrian blueprint unavailable")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)

        def spawn_at(point, yaw=0):
            waypoint = world.get_map().get_waypoint(carla.Location(x=point[0], y=point[1], z=0))
            z = waypoint.transform.location.z + .5 if waypoint else .5
            return carla.Transform(carla.Location(x=point[0], y=point[1], z=z), carla.Rotation(yaw=yaw))

        ego = world.spawn_actor(vehicles[0], spawn_at(scene["ego_start_xy_m"]))
        actors.append(ego)
        pedestrian = world.spawn_actor(walkers[0], spawn_at(scene["pedestrian_start_xy_m"], 90))
        actors.append(pedestrian)
        if ego is None or pedestrian is None or ego.id == pedestrian.id:
            raise ValueError("original vehicle and pedestrian identities not distinct")
        cameras = Cameras(world, ego, output, carla)
        capture = PipelineCapture(client, ego, output, scene["case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        collision_events = []
        collision = world.spawn_actor(library.find("sensor.other.collision"), carla.Transform(), attach_to=ego)
        actors.append(collision)
        collision.listen(lambda event: collision_events.append((event.frame, event.other_actor.id)))
        phase = "capturing"
        with (output / "encounter-history.jsonl").open("x", buffering=1) as stream:
            for index in range(round(scene["duration_s"] * scene["rate_hz"])):
                ego_body, ped_body = vertices(ego), vertices(pedestrian)
                approach_gap = max(0.0, min(v[0] for v in ped_body) - max(v[0] for v in ego_body))
                event = ({"source": "original_driver_input", "observed": True,
                          "kind": "scripted_observation_trigger", "input_gap_m": approach_gap}
                         if approach_gap <= scene["instrumented_observation_distance_m"] else None)
                sample = {"ego_body_vertices_m": ego_body, "pedestrian_body_vertices_m": ped_body,
                          "ego_speed_mps": speed(ego), "ego_brake": 0.0,
                          "ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
                          "pedestrian_class_source": walkers[0].id,
                          "driver_control_source": "scripted-driver-controller",
                          "driver_observation_event": event}
                measured = observed_encounter(site, sample)
                command = controller(measured, scene["response_policy"])
                ego.apply_control(carla.VehicleControl(throttle=command["throttle"],
                                                       brake=command["brake"], steer=command["steer"]))
                fraction = min(1.0, (index + 1) * scene["pedestrian_target_speed_mps"]
                               / scene["rate_hz"] / 2.0)
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
                              ego_speed_mps=speed(ego), ego_brake=command["brake"])
                value = observed_encounter(site, sample)
                row = {"frame": frame, "time_s": time_s, **sample,
                       "surface_gap_m": value["surface_gap_m"],
                       "contact_event": (frame, pedestrian.id) in collision_events,
                       "control_command": command}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                count += 1
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ["trace.jsonl", "video_frames.jsonl", "encounter-history.jsonl", "school-site.json",
                 "map.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, *_ in Cameras.SPECS]]
        write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": sha(output / name)}
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
                         context={"school_setting": site})
        else:
            write(output / "native-run-status.json",
                  {"phase": phase, "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
