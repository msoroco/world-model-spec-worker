"""Original Native four-view acquisition for the reviewed nighttime site.

The reviewed packet supplies physical carriage and person blueprints. This
module does not accept the assignment actor label as vehicle classification.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from night_parking_capture import capture_ticks, utc_start
from night_parking_construction import _inside


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


class Cameras:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, carla, subject, target, output, queue_capacity=4):
        if type(queue_capacity) is not int or not 1 <= queue_capacity <= 16:
            raise ValueError("bounded original camera queue capacity required")
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
                point = (carla.Location(x=dx, y=dy, z=z) if attached else
                         carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                sensor = world.spawn_actor(bp, carla.Transform(point, carla.Rotation(pitch=pitch)),
                                           attach_to=subject if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=queue_capacity)
                self.queues[name] = frames

                def receive(image, sink=frames, label=name):
                    try:
                        sink.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                           "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
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
        for name, encoder in self.encoders.items():
            try:
                if encoder.stdin and not encoder.stdin.closed:
                    encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    failures.append("encoder failed: " + name)
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


def _spawn(world, carla, blueprint, point, heading):
    waypoint = world.get_map().get_waypoint(carla.Location(x=point[0], y=point[1], z=0))
    if waypoint is None:
        raise ValueError("reviewed street placement absent in Native map")
    pose = carla.Transform(carla.Location(x=point[0], y=point[1],
                                          z=waypoint.transform.location.z + .5),
                           carla.Rotation(yaw=heading))
    actor = world.spawn_actor(world.get_blueprint_library().find(blueprint), pose)
    if actor.type_id != blueprint or math.dist(
            [actor.get_transform().location.x, actor.get_transform().location.y], point) > .5:
        raise ValueError("Native actor identity or placement differs from reviewed source")
    return actor


def run_native(config, packet_path, packet, plan, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir() or ".runtime-work" not in output.parts:
        raise ValueError("retained Native attempt must be under .runtime-work")
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    actors = []
    camera = pipeline = frame_map = None
    errors = []
    phase = "initializing"
    restored = False
    try:
        if (world.get_map().name != plan["native_map_name"] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
                != plan["native_opendrive_sha256"]):
            raise ValueError("Native OpenDRIVE differs from reviewed original")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        geo = packet["geometry"]
        native = packet["native_actors"]
        heading = float(geo.get("carriage_heading_deg", 0))
        subject = _spawn(world, carla, native["carriage_blueprint"],
                         geo["carriage_park_xy_m"], heading)
        actors.append(subject)
        other = _spawn(world, carla, native["other_vehicle_blueprint"],
                       geo["other_vehicle_xy_m"], float(geo.get("other_heading_deg", 0)))
        actors.append(other)
        person_xy = geo.get("responsible_person_xy_m")
        if not isinstance(person_xy, list) or len(person_xy) != 2:
            raise ValueError("reviewed responsible person placement required")
        person = _spawn(world, carla, native["responsible_person_blueprint"], person_xy, 0)
        actors.append(person)
        cargo = None
        if config["case"]["design"]["purpose"] == "loading":
            cargo = _spawn(world, carla, native["cargo_blueprint"],
                           geo["cargo_initial_xy_m"], 0)
            actors.append(cargo)
        classification = packet.get("classification", {})
        if (not all(type(classification.get(key)) is bool for key in
                    ("transport_capable", "self_propelled", "vehicle_exclusions_checked"))
                or classification["self_propelled"] != (config["case"]["design"]["vehicle_class"] == "motor")):
            raise ValueError("reviewed carriage classification differs from selected case")
        classification = dict(classification, physical_source=packet["sources"]["vehicle_build"]["sha256"])
        context = {"iana_timezone": "America/Los_Angeles",
                   "municipal_jurisdiction_source": packet["sources"]["municipal_boundary"]["sha256"],
                   "street_source": packet["sources"]["street_status"]["sha256"],
                   "reviewed_site_sha256": _sha(packet_path), "subject_actor_id": subject.id,
                   "other_vehicle_actor_id": other.id, "responsible_person_actor_id": person.id}
        _write(output / "context.json", context)
        _write(output / "classification.json", classification)
        _write(output / "acquisition-provenance.json", {
            "provenance_kind": "native", "diagnostic_fixture": False,
            "method": "reviewed original CARLA live run"})
        camera = Cameras(world, carla, subject, geo["carriage_park_xy_m"], output,
                         queue_capacity=config.get("capture_queue_capacity", 4))
        pipeline = PipelineCapture(client, subject, output, config["selected_case_id"])
        frame_map = FrameMap(output / "video_frames.jsonl")
        start = utc_start(packet["civil_date"], plan["civil_start_local_request"]) - dt.timedelta(seconds=2)
        street = geo["street_polygon_xy_m"]
        first, last = plan["parked_first_index"], plan["parked_last_index"]
        def before_tick(index):
            if cargo is None:
                return
            # A reviewed visible cargo prop and responsible person move through
            # a five-second transfer around the middle of the parked interval.
            midpoint = (first + last) // 2
            fraction = min(1.0, max(0.0, (index - midpoint + 50) / 100))
            start_xy, end_xy = geo["cargo_initial_xy_m"], geo["cargo_final_xy_m"]
            cargo_pose = cargo.get_transform()
            cargo_pose.location.x = start_xy[0] + fraction * (end_xy[0] - start_xy[0])
            cargo_pose.location.y = start_xy[1] + fraction * (end_xy[1] - start_xy[1])
            cargo.set_transform(cargo_pose)
            person_pose = person.get_transform()
            person_pose.location.x = person_xy[0] + fraction * (end_xy[0] - person_xy[0])
            person_pose.location.y = person_xy[1] + fraction * (end_xy[1] - person_xy[1])
            person.set_transform(person_pose)
        phase = "capturing"
        receipt = capture_ticks(world, subject, other, pipeline, camera, frame_map, output,
                                frame_count=plan["original_frame_count"], civil_start_utc=start,
                                subject_on_street=lambda actor: all(_inside(
                                    [float(vertex.x), float(vertex.y)], street)
                                    for vertex in actor.bounding_box.get_world_vertices(actor.get_transform())),
                                subject_parked=lambda index, actor: first <= index <= last and
                                    math.sqrt(sum(getattr(actor.get_velocity(), axis) ** 2
                                                  for axis in ("x", "y", "z"))) <= .15,
                                before_tick=before_tick)
        phase = "closing"
        pipeline.close(); pipeline = None
        frame_map.close(); frame_map = None
        camera.close(); camera = None
        activity = {"responsible_person_source": packet["sources"]["person_activity"]["sha256"],
                    "activity_source": "original responsible person, carriage and cargo acquisition" if cargo else
                                       "original responsible person and carriage acquisition",
                    "episode_start_event_source": "original selected 20 Hz schedule and body state",
                    "episode_end_event_source": "original selected 20 Hz schedule and body state",
                    "start_frame": receipt["first_native_frame"] + first,
                    "end_frame": receipt["first_native_frame"] + last,
                    "activity": config["case"]["design"]["purpose"]}
        _write(output / "activity.json", activity)
        names = {"context": "context.json", "classification": "classification.json",
                 "activity": "activity.json", "trace": "night-parking-trace.jsonl",
                 "frame_map": "video_frames.jsonl"}
        _write(output / "night-parking-sources.json", {
            "format": "night-parking-original-sources-v1",
            "sources": {key: {"path": name, "sha256": _sha(output / name)}
                        for key, name in names.items()}})
        originals = ["trace.jsonl", "night-parking-trace.jsonl", "video_frames.jsonl",
                     "context.json", "classification.json", "activity.json",
                     "night-parking-sources.json", "road.xodr", "carla_recorder.log",
                     *[name + ".mkv" for name, _, _ in Cameras.SPECS]]
        _write(output / "acquisition.json", {name: {"kind": "original_native", "sha256": _sha(output / name)}
                                                for name in originals})
        phase = "sealed"
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (pipeline, frame_map, camera):
            if resource is not None:
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
            seal_capture(output, frames=plan["original_frame_count"],
                         restoration={"restored": True,
                                      "settings_readback": "original world snapshot restored"},
                         errors=[], encoder_exit_codes={name: 0 for name, _, _ in Cameras.SPECS},
                         context={"night_parking": context, "episode_frames": [first, last]})
        else:
            _write(output / "native-run-status.json", {"phase": phase,
                  "errors": errors, "settings_restored": restored})
            if phase == "sealed":
                raise RuntimeError("Native cleanup or restoration failed")
