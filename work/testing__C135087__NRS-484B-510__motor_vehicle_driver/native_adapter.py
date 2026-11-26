"""Source-bound CARLA placement bridge for the restricted-zone cases.

This bridge deliberately leaves motion, original pixels and graph collection to
an injected capture adapter. It provides the concrete Native construction used
by that adapter, and refuses to change the world before reviewing its binding.
"""

import copy
import io
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import time

from site_geometry import load, point_at_station, station_of


def _inside_polygon(point, vertices):
    x, y = point[:2]
    inside = False
    for left, right in zip(vertices, vertices[1:] + vertices[:1]):
        x0, y0 = left
        x1, y1 = right
        if (y0 > y) != (y1 > y):
            crossing = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < crossing:
                inside = not inside
    return inside


class NativePlacement:
    def __init__(self, client, carla, plan, site_path):
        self.client, self.carla, self.plan = client, carla, plan
        self.site_path = Path(site_path)
        self.binding = load(site_path, plan)
        self.world = client.get_world()
        self.mapping = self.world.get_map()
        if self.mapping.name != self.binding["map_name"]:
            raise ValueError("live Native map differs from reviewed binding")
        for role, item in self.binding["fixed_actors"].items():
            actor = self.world.get_actors().find(item["actor_id"])
            if actor is None or actor.type_id != item["type_id"]:
                raise ValueError("live Native fixed actor differs: " + role)
        self.old_settings = copy.copy(self.world.get_settings())
        self.owned = []
        self.routes = {}
        self.schedule_entries = []
        self.sync_started = False

    def load_map(self, map_id):
        if map_id != self.plan.map_id or self.mapping.name != map_id:
            raise ValueError("Native map identity mismatch")
        settings = copy.copy(self.world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        readback = self.world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native 20 Hz world settings not confirmed")
        self.sync_started = True

    def mark_zone(self, start_m, end_m, purpose, source):
        if (start_m, end_m, purpose, source) != (
                self.plan.zone_start_m, self.plan.zone_end_m,
                self.plan.restricted_purpose, self.plan.restricted_source):
            raise ValueError("Native restricted-zone plan differs")
        for station in (start_m, end_m):
            point_at_station(self.binding, station)

    def _spawn(self, role, location, vehicle):
        if not self.sync_started:
            raise ValueError("Native world not synchronized")
        blueprint_id = self.binding["blueprints"][role]
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None:
            raise ValueError("reviewed Native blueprint unavailable: " + role)
        x, y, z = location
        place = self.carla.Location(x=x, y=y, z=z)
        if vehicle:
            waypoint = self.mapping.get_waypoint(place, project_to_road=False)
            if waypoint is None:
                raise ValueError("reviewed vehicle point has no live road waypoint")
            yaw = waypoint.transform.rotation.yaw
        else:
            yaw = float(self.binding.get("passenger_yaw_deg", 0))
        transform = self.carla.Transform(place, self.carla.Rotation(yaw=yaw))
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError("Native actor spawn/readback failed: " + role)
        self.owned.append(actor)
        if vehicle:
            actual = actor.get_transform().location
            observed = station_of(self.binding, (actual.x, actual.y, actual.z))
            target = self.plan.subject_stop_m if role == "subject" else self.plan.entrant_start_m
            if abs(observed - target) > self.binding["observation_tolerances_m"]["station"]:
                raise ValueError("Native vehicle spawn station readback differs")
        return actor

    def spawn_vehicle(self, role, station_m, vehicle_class):
        if role not in ("subject", "restricted-purpose-entrant"):
            raise ValueError("unknown vehicle role")
        key = "subject" if role == "subject" else "entrant"
        target = self.plan.subject_stop_m if key == "subject" else self.plan.entrant_start_m
        if station_m != target or not vehicle_class:
            raise ValueError("vehicle construction differs from reviewed plan")
        return self._spawn(key, point_at_station(self.binding, station_m), True)

    def spawn_pedestrian(self, role, station_m):
        if role != "passenger" or station_m != self.plan.subject_stop_m:
            raise ValueError("passenger construction differs from reviewed plan")
        return self._spawn("passenger", self.binding["passenger_spawn_m"], False)

    def set_route(self, actor, destination_m):
        if actor not in self.owned:
            raise ValueError("route actor not owned by this capture")
        if actor.type_id == self.binding["blueprints"]["passenger"]:
            self.routes[actor.id] = tuple(self.binding["passenger_door_m"])
        else:
            if destination_m != self.plan.entrant_destination_m:
                raise ValueError("entrant destination differs from reviewed plan")
            self.routes[actor.id] = point_at_station(self.binding, destination_m)

    def schedule(self, actor, action, at_s):
        if actor not in self.owned or not math.isfinite(float(at_s)) or at_s < 0:
            raise ValueError("Native schedule invalid")
        self.schedule_entries.append({"actor_id": actor.id, "action": action,
                                      "time_s": float(at_s)})

    def restore(self):
        failures = []
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except Exception as error:
                failures.append(str(error))
        self.owned.clear()
        if self.sync_started:
            try:
                self.world.apply_settings(self.old_settings)
                current = self.world.get_settings()
                if current.synchronous_mode != self.old_settings.synchronous_mode or \
                        current.fixed_delta_seconds != self.old_settings.fixed_delta_seconds:
                    failures.append("world settings restoration readback differs")
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise ValueError("Native restoration failed: " + "; ".join(failures))
        return True


class OriginalAdapter:
    """Single tick owner for live CARLA frames and source-derived observations."""

    VIEWS = ("overview", "approach", "reference_corner", "driver_reference")

    def __init__(self, host, port, config, plan, site_path, *, carla_module=None,
                 client_factory=None, capture_factory=None):
        if carla_module is None:
            import carla
            carla_module = carla
        self.carla = carla_module
        self.client = (client_factory or self.carla.Client)(host, int(port))
        self.client.set_timeout(30.0)
        self.world = NativePlacement(self.client, self.carla, plan, site_path)
        self.config, self.plan = config, plan
        self.capture_factory = capture_factory
        self.actors = None
        self.sensors = {}
        self.camera_queues = {}
        self.encoders = {}
        self.pipeline = None
        self.start_time = None
        self.last_frame = None
        self.sample_index = 0
        self.closed = False
        self.completed = False

    def provenance(self):
        return "original_native"

    def _location(self, actor):
        value = actor.get_transform().location
        return (float(value.x), float(value.y), float(value.z))

    def _speed(self, actor):
        value = actor.get_velocity()
        return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)

    def _encoder(self, path, width, height):
        return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error",
                                 "-f", "rawvideo", "-pixel_format", "bgra",
                                 "-video_size", f"{width}x{height}", "-framerate", "20",
                                 "-i", "pipe:0", "-an", "-c:v", "ffv1", str(path)],
                                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE)

    def attach_cameras(self, actors, views):
        if set(views) != set(self.VIEWS) or set(actors) != {"subject", "entrant", "passenger"}:
            raise ValueError("Native participant or four-view construction incomplete")
        self.actors = actors
        output = Path.cwd()
        for spec in self.config["cameras"]:
            view = spec["name"]
            blueprint = self.world.world.get_blueprint_library().find("sensor.camera.rgb")
            if blueprint is None:
                raise ValueError("Native RGB sensor blueprint missing")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            pose = self.world.binding["camera_poses"][view]
            x, y, z = pose["location_m"]
            pitch, yaw, roll = pose["rotation_deg"]
            transform = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                             self.carla.Rotation(pitch=pitch, yaw=yaw,
                                                                 roll=roll))
            sensor = self.world.world.try_spawn_actor(blueprint, transform)
            if sensor is None or sensor.type_id != "sensor.camera.rgb":
                raise ValueError("Native RGB sensor spawn/readback failed: " + view)
            self.world.owned.append(sensor)
            self.sensors[view] = sensor
            inbox = queue.Queue()
            self.camera_queues[view] = inbox
            sensor.listen(lambda image, target=inbox: target.put(image))
            self.encoders[view] = self._encoder(output / (view + ".mkv"),
                                                spec["width"], spec["height"])
        spec = self.config["cameras"][0]
        self.encoders["raw"] = self._encoder(output / "raw.mkv",
                                              spec["width"], spec["height"])
        if self.capture_factory is None:
            from pipeline_capture import PipelineCapture
            self.capture_factory = PipelineCapture
        self.pipeline = self.capture_factory(self.client, actors["subject"], output,
                                             self.plan.case_id,
                                             required_observations=self.config.get("required_atoms", ()))
        return self.sensors

    def _control_vehicle(self, actor, moving, target_station):
        station = station_of(self.world.binding, self._location(actor))
        if moving and station < target_station - .5:
            control = self.carla.VehicleControl(throttle=.25, brake=0.0)
        else:
            control = self.carla.VehicleControl(throttle=0.0, brake=1.0)
        actor.apply_control(control)

    def request_control(self, actors, plan, index):
        if actors is not self.actors or plan is not self.plan or index < 0:
            raise ValueError("Native control request differs from construction")
        t = index / 20.0
        self._control_vehicle(actors["subject"], t >= plan.subject_departure_s,
                              plan.zone_end_m + 5)
        self._control_vehicle(actors["entrant"], t >= plan.entrant_departure_s,
                              plan.entrant_destination_m)
        passenger = actors["passenger"]
        door = self.world.binding["passenger_door_m"]
        current = self._location(passenger)
        delta = tuple(b - a for a, b in zip(current, door))
        distance = math.dist(current, door)
        walking = plan.passenger_exchange_start_s <= t <= plan.passenger_exchange_end_s
        if walking and distance > .2:
            direction = tuple(d / distance for d in delta)
            speed = min(1.0, distance / .05)
        else:
            direction, speed = (0.0, 0.0, 0.0), 0.0
        passenger.apply_control(self.carla.WalkerControl(
            direction=self.carla.Vector3D(*direction), speed=speed))

    def _camera_image(self, view, frame, time_s):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            image = self.camera_queues[view].get(timeout=max(.01, deadline-time.monotonic()))
            if image.frame == frame:
                if abs(float(image.timestamp) - time_s) > .005:
                    raise ValueError("Native camera timestamp differs: " + view)
                return image
            if image.frame > frame:
                raise ValueError("Native camera skipped frame: " + view)
        raise ValueError("Native camera timed out: " + view)

    def tick_and_read(self, actors, cameras):
        if actors is not self.actors or cameras is not self.sensors:
            raise ValueError("Native camera/actor identity differs")
        index = self.sample_index
        frame = self.world.world.tick()
        snapshot = self.world.world.get_snapshot()
        if snapshot.frame != frame or (self.last_frame is not None and frame != self.last_frame + 1):
            raise ValueError("Native world frame discontinuity")
        self.last_frame = frame
        time_s = float(snapshot.timestamp.elapsed_seconds)
        if self.start_time is None:
            self.start_time = time_s
        trace = self.pipeline.capture(frame, time_s)
        from PIL import Image
        pixels = {}
        for view in self.VIEWS:
            image = self._camera_image(view, frame, time_s)
            raw = bytes(image.raw_data)
            if self.encoders[view].stdin.write(raw) != len(raw):
                raise ValueError("Native RGB encoder short write: " + view)
            if view == "overview":
                if self.encoders["raw"].stdin.write(raw) != len(raw):
                    raise ValueError("Native raw encoder short write")
            picture = Image.frombytes("RGBA", (image.width, image.height), raw, "raw", "BGRA")
            buffer = io.BytesIO()
            picture.convert("RGB").save(buffer, format="PNG")
            pixels[view] = buffer.getvalue()
        subject, entrant, passenger = (actors[k] for k in ("subject", "entrant", "passenger"))
        subject_station = station_of(self.world.binding, self._location(subject))
        entrant_station = station_of(self.world.binding, self._location(entrant))
        passenger_location = self._location(passenger)
        passenger_station = station_of(self.world.binding, passenger_location)
        door_distance = math.dist(passenger_location, self.world.binding["passenger_door_m"])
        at_door = door_distance <= self.world.binding["observation_tolerances_m"]["door"]
        parent = passenger.get_parent() if hasattr(passenger, "get_parent") else None
        aboard = parent is not None and parent.id == subject.id
        passenger_state = "aboard" if aboard else "at_door" if at_door else "approaching"
        entrant_speed = self._speed(entrant)
        access_range = self.world.binding["observation_tolerances_m"]["access"]
        near_access = self.plan.zone_start_m - access_range <= entrant_station < self.plan.zone_start_m
        entrant_waiting = near_access and entrant_speed < .1
        subject_in_access = _inside_polygon(self._location(subject),
                                             self.world.binding["entrant_access_polygon_m"])
        state = {"case_id": self.plan.case_id, "map_id": self.plan.map_id,
                 "subject_station_m": subject_station, "subject_speed_mps": self._speed(subject),
                 "entrant_station_m": entrant_station, "entrant_speed_mps": entrant_speed,
                 "entrant_waiting": entrant_waiting,
                 "passenger_exchange_active": at_door and not aboard,
                 "passenger_station_m": passenger_station,
                 "passenger_boarding_state": passenger_state,
                 "entrant_access_blocked": near_access and subject_in_access,
                 "entrant_parking_task_active": True}
        self.sample_index += 1
        return {"frame": frame, "time_s": time_s, "state": state,
                "camera_png": pixels, "trace": trace,
                "video_frame": {"video_frame": index,
                                "carla_frame": frame, "time_s": time_s}}

    def finalize_media(self, output, views, mappings):
        if len(mappings) != 900:
            raise ValueError("original video frame map incomplete")
        result = {}
        for view, process in self.encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) != 0:
                raise ValueError("Native RGB encoding failed: " + view + ": " +
                                 stderr.decode(errors="replace")[-500:])
            result[view] = Path(output) / (view + ".mkv")
        return result

    def finalize_native_capture(self, output, rows, traces):
        if len(rows) != 900 or self.pipeline is None:
            raise ValueError("original Native graph history incomplete")
        self.pipeline.close(confirmed=True)
        manifest = Path(output) / "capture/manifest.json"
        if json.loads(manifest.read_text()).get("frames") != 900:
            raise ValueError("original Native graph manifest incomplete")
        self.completed = True
        return manifest

    def close(self):
        if self.closed:
            return False
        self.closed = True
        errors = []
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except Exception as error:
                errors.append(str(error))
        if self.pipeline is not None:
            try:
                self.pipeline.close(confirmed=self.completed and not errors)
            except Exception as error:
                errors.append(str(error))
        for process in self.encoders.values():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        try:
            self.world.restore()
        except Exception as error:
            errors.append(str(error))
        if errors:
            raise ValueError("Native adapter close failed: " + "; ".join(errors))
        return True


def create_adapter(host, port, config, plan):
    site_path = os.environ.get("SCENARIO_RESTRICTED_ZONE_SITE")
    if not site_path:
        raise ValueError("independent restricted-zone site packet required")
    return OriginalAdapter(host, port, config, plan, site_path)
