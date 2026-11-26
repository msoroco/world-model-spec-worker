"""Original CARLA parking capture with body, device and four camera readback."""

from __future__ import annotations

import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from parking_place import _footprint, _inside, _overlaps, _polygon


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def xy_body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    x = [v.x for v in vertices]
    y = [v.y for v in vertices]
    return [[min(x), min(y)], [max(x), min(y)], [max(x), max(y)], [min(x), max(y)]]


def speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def control(distance_m, speed_mps, phase, conduct):
    """Finite engineering controller; it does not classify legal conduct."""
    if phase == "hold":
        return {"throttle": 0.0, "brake": 1.0, "hand_brake": conduct == "park"}
    if phase == "depart":
        return {"throttle": 0.22 if speed_mps < 4.0 else 0.0,
                "brake": 0.0, "hand_brake": False}
    stopping_distance = speed_mps * speed_mps / 5.0 + 1.0
    if distance_m <= stopping_distance:
        return {"throttle": 0.0, "brake": 0.65, "hand_brake": False}
    return {"throttle": 0.28 if speed_mps < 5.0 else 0.0,
            "brake": 0.0, "hand_brake": False}


def phase_for(conduct, reached, hold_frames, duration_frames):
    """Engineering episode schedule; frame counts are not statutory definitions."""
    if conduct not in ("stop", "stand", "park"):
        raise ValueError("unknown conduct construction")
    if not reached:
        return "approach"
    planned_hold = {"stop": 60, "stand": 160, "park": duration_frames}[conduct]
    return "depart" if conduct != "park" and hold_frames >= planned_hold else "hold"


def verify_road_feature(mapping, carla, place_record):
    """Compare reviewed physical road samples with the loaded Native map."""
    feature = place_record.get("feature")
    if feature not in ("curve", "restricted_width"):
        raise ValueError("unsupported reviewed road feature")
    measurement = place_record.get("feature_measurement")
    if not isinstance(measurement, dict) or not isinstance(measurement.get("samples"), list):
        raise ValueError("reviewed road feature samples required")
    samples = measurement["samples"]
    if len(samples) < 2:
        raise ValueError("two reviewed road feature samples required")
    headings = []
    widths = []
    for sample in samples:
        if not isinstance(sample, dict) or not all(k in sample for k in
            ("x", "y", "road_id", "lane_width_m", "heading_deg")):
            raise ValueError("reviewed road feature sample incomplete")
        waypoint = mapping.get_waypoint(carla.Location(x=sample["x"], y=sample["y"], z=0))
        if waypoint is None or waypoint.road_id != sample["road_id"]:
            raise ValueError("reviewed road feature road identity differs")
        yaw = waypoint.transform.rotation.yaw
        width = waypoint.lane_width
        if (abs(((yaw - sample["heading_deg"] + 180) % 360) - 180) > 3 or
                abs(width - sample["lane_width_m"]) > 0.15):
            raise ValueError("reviewed road feature geometry differs from Native map")
        headings.append(yaw)
        widths.append(width)
    if feature == "curve":
        turn = abs(((headings[-1] - headings[0] + 180) % 360) - 180)
        if turn < 15:
            raise ValueError("reviewed curve not physically present")
    elif max(widths) > 3.0:
        raise ValueError("reviewed restricted width not physically present")
    return {"feature": feature, "sample_count": len(samples),
            "readback_lane_widths_m": widths, "readback_headings_deg": headings}


def verify_traffic_actor(actor, reviewed_pose):
    actual = actor.get_transform()
    expected = (reviewed_pose["x"], reviewed_pose["y"], reviewed_pose["z"])
    observed = (actual.location.x, actual.location.y, actual.location.z)
    if math.dist(expected, observed) > 0.5:
        raise ValueError("reviewed traffic actor pose differs from Native readback")
    if abs(((actual.rotation.yaw - reviewed_pose["yaw_deg"] + 180) % 360) - 180) > 3:
        raise ValueError("reviewed traffic actor heading differs from Native readback")


class Cameras:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, carla, ego, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 2, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                pose = carla.Transform(location, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, pose, attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                        f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                        "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(args, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame differs from original world frame: " + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        failures = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                failures.append(repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    failures.append("camera encoder failed: " + name)
            except BaseException as error:
                failures.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                failures.append(repr(error))
        self.sensors = []
        self.encoders = {}
        if failures:
            raise RuntimeError("; ".join(failures))


def _source(site_path, site, kind):
    return json.loads((Path(site_path).parent / site["sources"][kind]["path"]).read_text(encoding="utf-8"))


def run_native(cfg, site, site_path, placement, output, host, port):
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
    original_settings = world.get_settings()
    actors = []
    cameras = capture = frame_map = None
    phase = "initializing"
    errors = []
    restored = False
    rows = []
    try:
        map_record = _source(site_path, site, "map")
        map_bytes = world.get_map().to_opendrive().encode()
        if (world.get_map().name != site["map_id"] or
                hashlib.sha256(map_bytes).hexdigest() != map_record.get("opendrive_sha256")):
            raise ValueError("reviewed map does not match current Native world")
        device_record = _source(site_path, site, "device")
        place_record = _source(site_path, site, "place_facts")
        candidate = site["parking_candidates"][cfg["selected_case_id"].split("__")[-1]]
        target = candidate["center"]
        start = candidate.get("approach_center")
        if not isinstance(start, list) or len(start) != 2 or math.dist(start, target) < 8:
            raise ValueError("reviewed approach center at least 8 m before target required")
        mapping = world.get_map()
        start_wp = mapping.get_waypoint(carla.Location(x=start[0], y=start[1], z=0))
        target_wp = mapping.get_waypoint(carla.Location(x=target[0], y=target[1], z=0))
        if not start_wp or not target_wp or start_wp.road_id != target_wp.road_id:
            raise ValueError("Native approach and target are not on the reviewed road")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        vehicle_id = site.get("vehicle_blueprint_id", "vehicle.tesla.model3")
        vehicle_bp = library.find(vehicle_id)
        prop_id = device_record.get("prop_blueprint_id")
        prop_pose = device_record.get("prop_pose")
        if not prop_id or not isinstance(prop_pose, dict):
            raise ValueError("physical device prop identity and pose required")
        prop_bp = library.find(prop_id)

        def pose(values):
            return carla.Transform(carla.Location(x=values["x"], y=values["y"], z=values["z"]),
                                   carla.Rotation(yaw=values["yaw_deg"]))

        prop = world.spawn_actor(prop_bp, pose(prop_pose))
        actors.append(prop)
        if prop.type_id != prop_id:
            raise ValueError("Native device prop readback differs")
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=start[0], y=start[1], z=start_wp.transform.location.z + 0.5),
            carla.Rotation(yaw=candidate["heading_deg"])))
        actors.append(ego)
        if ego.type_id != vehicle_id:
            raise ValueError("Native vehicle blueprint readback differs")
        curb_start = site.get("curb_person_start")
        curb_end = site.get("curb_person_end")
        if (not isinstance(curb_start, list) or not isinstance(curb_end, list)
                or len(curb_start) != 2 or len(curb_end) != 2
                or math.dist(curb_start, curb_end) < 2):
            raise ValueError("source-bound curb person path required for conduct contrast")
        walkers = list(library.filter("walker.pedestrian.*"))
        if not walkers:
            raise ValueError("Native curb person blueprint unavailable")
        person_initial = curb_end if site["requested_conduct"] == "stop" else curb_start
        person = world.spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=person_initial[0], y=person_initial[1], z=0.5)))
        actors.append(person)
        feature_readback = None
        if place_record.get("feature") == "traffic_queue":
            traffic_poses = place_record.get("traffic_vehicle_poses", [])
            if len(traffic_poses) < 2:
                raise ValueError("congested scene requires two source-bound traffic actors")
            traffic_ids = []
            for queue_pose in traffic_poses:
                traffic = world.spawn_actor(vehicle_bp, pose(queue_pose))
                actors.append(traffic)
                verify_traffic_actor(traffic, queue_pose)
                traffic_ids.append(traffic.id)
            feature_readback = {"feature": "traffic_queue", "traffic_actor_ids": traffic_ids}
        elif place_record.get("feature") in ("curve", "restricted_width"):
            feature_readback = verify_road_feature(mapping, carla, place_record)
        else:
            raise ValueError("hazard or congestion physical feature unconstructed")
        context = {"assignment_id": cfg["assignment_id"], "case_id": cfg["selected_case_id"],
                   "map_id": site["map_id"], "device_id": site["device_id"],
                   "designated_place_id": site["designated_place_id"],
                   "designated_place_polygon": site["designated_place_polygon"],
                   "official_authority_source": site["sources"]["authority"]["sha256"],
                   "device_instructions_source": site["sources"]["device"]["sha256"],
                   "hazard_or_congestion_source": site["sources"]["place_facts"]["sha256"],
                   "hazard_or_congestion_status": site["place_context_for_review"],
                   "device_erected": True, "device_actor_id": prop.id,
                   "vehicle_actor_id": ego.id, "parker_actor_id": ego.id,
                   "curb_person_actor_id": person.id,
                   "curb_person_blueprint": walkers[0].id,
                   "site_sha256": sha(site_path), "place_feature": place_record["feature"],
                   "place_feature_readback": feature_readback,
                   "approach_road_id": start_wp.road_id, "target_road_id": target_wp.road_id,
                   "loading_activity_source": "original four-camera plus control history",
                   "officer_or_device_direction_source": site["sources"]["device"]["sha256"]}
        write(output / "parking-context.json", context)
        write(output / "acquisition-provenance.json", {"provenance_kind": "native",
              "diagnostic_fixture": False, "method": "original CARLA live run"})
        cameras = Cameras(world, carla, ego, target, output)
        capture = PipelineCapture(client, ego, output, cfg["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        zone = _polygon(site["designated_place_polygon"])
        phase = "capturing"
        reached = False
        hold_frames = 0
        with (output / "parking-history.jsonl").open("x", buffering=1) as stream:
            for index in range(round(cfg["duration_s"] * cfg["rate_hz"])):
                distance = math.dist([ego.get_transform().location.x, ego.get_transform().location.y], target)
                body = xy_body(ego)
                wholly_inside = all(_inside(p, zone) for p in body)
                wholly_outside = not _overlaps(body, zone)
                wanted_inside = candidate["requested_wholly_within_place"]
                if distance <= 1.5 and (wholly_inside if wanted_inside else wholly_outside):
                    reached = True
                conduct = site["requested_conduct"]
                phase_name = phase_for(conduct, reached, hold_frames,
                                       round(cfg["duration_s"] * cfg["rate_hz"]))
                command = control(distance, speed(ego), phase_name, site["requested_conduct"])
                ego.apply_control(carla.VehicleControl(**command))
                if phase_name == "hold" and conduct in ("stop", "park"):
                    fraction = min(1.0, hold_frames / (60 if conduct == "stop" else 160))
                    if conduct == "stop":
                        fraction = 1.0 - fraction
                    position = [curb_start[j] + fraction * (curb_end[j] - curb_start[j])
                                for j in range(2)]
                    person.set_transform(carla.Transform(carla.Location(
                        x=position[0], y=position[1], z=0.5)))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("Native frame identity changed")
                time_s = snap.timestamp.elapsed_seconds
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                body = xy_body(ego)
                stationary = speed(ego) <= 0.1
                if phase_name == "hold" and stationary:
                    hold_frames += 1
                row = {"frame": frame, "time_s": time_s,
                       "vehicle_footprint": body, "speed_mps": speed(ego),
                       "position_m": [ego.get_transform().location.x, ego.get_transform().location.y],
                       "vehicle_actor_id": ego.id, "device_actor_id": prop.id,
                       "curb_person_actor_id": person.id,
                       "curb_person_position_m": [person.get_transform().location.x,
                                                  person.get_transform().location.y],
                       "curb_person_body_m": xy_body(person),
                       "control_command": command, "phase": phase_name,
                       "requested_conduct": site["requested_conduct"],
                       "loading_activity_observed": None,
                       "officer_direction_observed": None}
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                rows.append(row)
        phase = "closing"
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ["trace.jsonl", "video_frames.jsonl", "parking-history.jsonl",
                 "parking-context.json", "road.xodr", "carla_recorder.log",
                 *[name + ".mkv" for name, _, _ in Cameras.SPECS]]
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
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            restored = restore(client, saved_world)["restored"]
        except BaseException as error:
            errors.append(repr(error))
        if phase == "sealed" and not errors and restored:
            seal_capture(output, frames=len(rows), restoration={"restored": True,
                "settings_readback": "original world snapshot restored"}, errors=[],
                encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                context={"parking": context, "hold_frames": hold_frames})
        else:
            write(output / "native-run-status.json", {"phase": phase, "errors": errors,
                                                     "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
