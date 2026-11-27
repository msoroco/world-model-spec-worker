"""Original CARLA acquisition for the roadside sidewalk pedestrian pair.

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


class Recorder:
    """Own the original CARLA recorder until its bytes are closed and readable."""

    def __init__(self, client, path):
        self.client, self.path, self.active = client, Path(path), False
        if self.path.exists():
            raise ValueError("original CARLA recorder path already exists")
        client.start_recorder(str(self.path), True)
        self.active = True

    def close(self):
        if not self.active:
            return
        self.client.stop_recorder()
        self.active = False
        if not self.path.is_file() or self.path.stat().st_size == 0:
            raise ValueError("original CARLA recorder bytes absent after stop")


def inspect_road(world, carla, scene, output):
    mapping = world.get_map()
    road_samples, sidewalk_samples, opposing_samples = [], [], []
    start_x = round(scene["ego_start_xy_m"][0])
    end_x = round(scene["ego_end_xy_m"][0])
    if start_x >= end_x:
        raise ValueError("authored ego route direction changed")
    stations = list(range(start_x, end_x + 1, 5))
    if stations[-1] != end_x:
        stations.append(end_x)
    for x in stations:
        point = carla.Location(x=float(x), y=0.0, z=0.0)
        waypoint = mapping.get_waypoint(point)
        if waypoint is None or math.hypot(waypoint.transform.location.x - x,
                                         waypoint.transform.location.y) > 1.5:
            raise ValueError("authored ego route absent from original Native road")
        if waypoint.lane_type != carla.LaneType.Driving or abs(
            (waypoint.transform.rotation.yaw + 180) % 360 - 180
        ) > 10:
            raise ValueError("original ego lane does not drive along authored route")
        adjacent = [getattr(waypoint, direction)()
                    for direction in ("get_left_lane", "get_right_lane")]
        sidewalks = [lane for lane in adjacent if lane is not None
                     and lane.lane_type == carla.LaneType.Sidewalk]
        if len(sidewalks) != 1:
            raise ValueError("original Native roadside sidewalk is absent or ambiguous")
        opposing = [lane for lane in adjacent if lane is not None
                    and lane.lane_type == carla.LaneType.Driving
                    and lane.road_id == waypoint.road_id
                    and lane.lane_id * waypoint.lane_id < 0]
        if len(opposing) != 1 or any(
            lane is not None and lane not in sidewalks and lane not in opposing
            for lane in adjacent
        ):
            raise ValueError("original Native road is not one driving lane per direction")
        opposite = opposing[0]
        if abs((opposite.transform.rotation.yaw + 180) % 360 - 180) < 170:
            raise ValueError("original opposing lane does not face against authored route")
        if any(
            neighbor is not None and neighbor.lane_type == carla.LaneType.Driving
            and neighbor.road_id == waypoint.road_id
            and neighbor.lane_id * opposite.lane_id > 0
            and neighbor.lane_id != opposite.lane_id
            for neighbor in (opposite.get_left_lane(), opposite.get_right_lane())
        ):
            raise ValueError("original Native opposing direction has additional driving lanes")
        sidewalk = sidewalks[0]
        if sidewalk.road_id != waypoint.road_id or not math.isfinite(sidewalk.lane_width):
            raise ValueError("original Native sidewalk is not adjacent to reviewed road")
        sidewalk_samples.append(sidewalk)
        road_samples.append(waypoint)
        opposing_samples.append(opposing[0])
    if len({item.road_id for item in road_samples}) != 1:
        raise ValueError("ego route not on one original road")
    if len({item.lane_id for item in road_samples}) != 1 or len({item.lane_id for item in opposing_samples}) != 1:
        raise ValueError("driving lane identities change along original road")
    if any(not math.isfinite(item.lane_width) or item.lane_width < 3 for item in opposing_samples):
        raise ValueError("opposing driving lane width invalid")
    width = min(item.lane_width for item in road_samples)
    if not math.isfinite(width) or width < 3:
        raise ValueError("original road width cannot support authored roadside encounter")
    if len({item.lane_id for item in sidewalk_samples}) != 1:
        raise ValueError("sidewalk lane identity changes along original road")
    side_width = min(item.lane_width for item in sidewalk_samples)
    side_y = [item.transform.location.y for item in sidewalk_samples]
    if side_width <= 0 or max(side_y) - min(side_y) > 0.5:
        raise ValueError("sidewalk alignment or width cannot support authored route")
    side_center = sum(side_y) / len(side_y)
    side_bounds = [side_center - side_width / 2, side_center + side_width / 2]
    driving_samples = road_samples + opposing_samples
    road_bounds = [min(item.transform.location.y - item.lane_width / 2 for item in driving_samples),
                   max(item.transform.location.y + item.lane_width / 2 for item in driving_samples)]
    if not (side_bounds[1] < road_bounds[0] or side_bounds[0] > road_bounds[1]):
        raise ValueError("sidewalk overlaps the original road edge")
    source = output / "map.xodr"
    source.write_text(mapping.to_opendrive())
    site = {"format": "worker-near-road-site", "cell_id": "C416422",
            "layout": "single_lane_per_direction", "sidewalk_present": True,
            "map_source": {"path": "map.xodr", "sha256": sha(source)},
            "road": {"lateral_bounds_m": road_bounds,
                     "classification_source": "original Native driving-lane waypoint road_id",
                     "edge_review_source": "original Native lane_width along route"},
            "sidewalk": {"lateral_bounds_m": side_bounds,
                         "lane_source": "original Native adjacent Sidewalk lane_type and lane_id",
                         "adjacency_source": "original Native waypoint neighbor at every sampled station"},
            "ego_start_xy_m": scene["ego_start_xy_m"], "ego_end_xy_m": scene["ego_end_xy_m"],
            "pedestrian_start_xy_m": scene["pedestrian_start_xy_m"],
            "pedestrian_end_xy_m": scene["pedestrian_end_xy_m"],
            "road_id": road_samples[0].road_id,
            "sample_lane_ids": [item.lane_id for item in road_samples],
            "sample_lane_widths_m": [item.lane_width for item in road_samples],
            "sample_opposing_lane_ids": [item.lane_id for item in opposing_samples],
            "sample_opposing_lane_widths_m": [item.lane_width for item in opposing_samples],
            "sample_sidewalk_lane_ids": [item.lane_id for item in sidewalk_samples],
            "sample_sidewalk_lane_widths_m": [item.lane_width for item in sidewalk_samples]}
    from road_scene import load_site
    write(output / "road-site.json", site)
    load_site(output / "road-site.json")
    return site


class Cameras:
    SPECS = (("overview", 1920, 1080, (0, 0, 45, -90, 0)),
             ("approach", 1280, 720, (-15, -12, 12, -25, 35)),
             ("reference_corner", 1280, 720, (-8, 8, 10, -30, -30)),
             ("driver_reference", 1280, 720, (0, 0, 2, 0, 0)))

    def __init__(self, world, ego, output, carla):
        self.sensors, self.encoders, self.queues = [], {}, {}
        try:
            for name, width, height, pose in self.SPECS:
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                x, y, z, pitch, yaw = pose
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch, yaw=yaw))
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


def spawn_at(mapping, carla, site, point, yaw=0, sidewalk=False):
    location = carla.Location(x=point[0], y=point[1], z=0)
    waypoint = (mapping.get_waypoint(location, project_to_road=False,
                lane_type=carla.LaneType.Sidewalk) if sidewalk
                else mapping.get_waypoint(location))
    if waypoint is None or waypoint.road_id != site["road_id"] or (
        waypoint.lane_type != (carla.LaneType.Sidewalk if sidewalk else carla.LaneType.Driving)
    ) or waypoint.lane_id not in site[
        "sample_sidewalk_lane_ids" if sidewalk else "sample_lane_ids"
    ]:
        raise ValueError("original Native route waypoint differs from reviewed road site")
    if math.hypot(waypoint.transform.location.x - point[0],
                  waypoint.transform.location.y - point[1]) > waypoint.lane_width / 2:
        raise ValueError("authored spawn falls outside reviewed Native lane")
    z = waypoint.transform.location.z + .5
    return carla.Transform(carla.Location(x=point[0], y=point[1], z=z), carla.Rotation(yaw=yaw))


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
    actors, cameras, capture, frame_map, recorder = [], None, None, None, None
    phase, errors, count, restored = "initializing", [], 0, False
    try:
        site = inspect_road(world, carla, scene, output)
        library = world.get_blueprint_library()
        vehicles = list(library.filter(scene["ego_blueprint_filter"]))
        walkers = list(library.filter(scene["pedestrian_blueprint_filter"]))
        if not vehicles or not walkers:
            raise ValueError("original Native vehicle or pedestrian blueprint unavailable")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        recorder = Recorder(client, output / "carla_recorder.log")

        ego = world.spawn_actor(vehicles[0], spawn_at(world.get_map(), carla, site,
                                                       scene["ego_start_xy_m"]))
        actors.append(ego)
        pedestrian = world.spawn_actor(walkers[0], spawn_at(world.get_map(), carla, site,
                                                             scene["pedestrian_start_xy_m"], 0, True))
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
                pedestrian.set_transform(spawn_at(world.get_map(), carla, site, destination, 0, True))
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
        recorder.close(); recorder = None
        names = ["trace.jsonl", "video_frames.jsonl", "encounter-history.jsonl", "road-site.json",
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
        if recorder:
            try:
                recorder.close()
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
                         context={"single_lane_per_direction_sidewalk": site})
        else:
            write(output / "native-run-status.json",
                  {"phase": phase, "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
