"""Source-gated CARLA session for the C111125 motorcycle straight cases.

The reviewed observer is original, SHA-bound operator code. It must read the
composite official head, detector/fault evidence and participant regions from
the live world. Standard CARLA traffic-light state alone cannot establish a
simultaneous steady red and green turn arrow, so no state is inferred here.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
from queue import Empty, Queue
from types import ModuleType

from signal_exception import require, sealed, verify_site

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _load_observer(site, root):
    name = site.get("observer_source_ref")
    require(name in site["original_sources"], "reviewed Native observer source missing")
    source = sealed(site["original_sources"][name], root)
    module = ModuleType("reviewed_c111125_observer")
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), module.__dict__)
    for method in ("control", "read_composite_head", "read_participants"):
        require(callable(getattr(module, method, None)), "reviewed observer lacks " + method)
    return module


def _mount(carla, value):
    require(isinstance(value, dict), "reviewed camera mount required")
    xyz, angles = value.get("xyz"), value.get("pitch_yaw_roll")
    require(isinstance(xyz, list) and len(xyz) == 3 and
            isinstance(angles, list) and len(angles) == 3 and
            all(type(v) in (int, float) and math.isfinite(v) for v in xyz + angles),
            "finite reviewed camera mount required")
    return carla.Transform(carla.Location(*xyz), carla.Rotation(*angles))


class Session:
    def __init__(self, world, carla, site, observer):
        self.world, self.carla = world, carla
        self.blueprint_library = world.get_blueprint_library()
        self.site, self.observer = site, observer
        self.event_adapter = self
        self.camera_adapter = self
        self.ego = self.head = None
        self.sensors = {}
        self.queues = {}
        self.index = 0

    def bind_native(self, native, site):
        require(self.ego is None and site == self.site, "Native binding changed")
        self.ego, self.head = native["ego"], native["head"]
        cameras = site.get("camera_mounts")
        require(isinstance(cameras, dict) and set(cameras) == set(VIEWS),
                "four reviewed camera mounts required")
        require(site.get("camera_source_ref") in site["original_sources"],
                "camera mount source missing")
        try:
            for name in VIEWS:
                entry = cameras[name]
                require(type(entry.get("width")) is int and entry["width"] >= 16 and
                        type(entry.get("height")) is int and entry["height"] >= 16 and
                        type(entry.get("fov")) in (int, float) and
                        math.isfinite(entry["fov"]) and 1 < entry["fov"] < 179,
                        "reviewed camera optical parameters required")
                bp = self.blueprint_library.find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(entry["width"]))
                bp.set_attribute("image_size_y", str(entry["height"]))
                bp.set_attribute("fov", str(entry["fov"]))
                bp.set_attribute("sensor_tick", "0.05")
                sensor = self.world.spawn_actor(bp, _mount(self.carla, entry["mount"]),
                                                attach_to=self.ego)
                require(sensor is not None, "Native camera spawn failed")
                queue = Queue()
                sensor.listen(queue.put)
                self.sensors[name], self.queues[name] = sensor, queue
        except Exception:
            self.close()
            raise

    def tick(self):
        require(self.ego is not None and len(self.sensors) == 4, "Native actor/cameras not bound")
        command = self.observer.control(self.world, self.ego, self.head, self.site, self.index)
        require(isinstance(command, dict) and command.get("source_kind") == "reviewed_native_controller",
                "reviewed original controller output required")
        throttle, brake, steer = (command.get(key) for key in ("throttle", "brake", "steer"))
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (throttle, brake, steer)) and
                0 <= throttle <= 1 and 0 <= brake <= 1 and -1 <= steer <= 1 and
                not (throttle > 0 and brake > 0), "invalid reviewed Native control")
        self.ego.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        require(frame == snapshot.frame, "Native tick/snapshot frame mismatch")
        aspects = self.observer.read_composite_head(self.world, self.head, self.site, frame)
        require(isinstance(aspects, dict) and aspects.get("source_kind") == "native_device_readback" and
                aspects.get("official_head_id") == self.site["official_head_id"],
                "original composite head readback required")
        users = self.observer.read_participants(self.world, self.site, frame)
        require(isinstance(users, list) and all(isinstance(u, dict) and
                u.get("source_kind") == "native_world_snapshot" for u in users),
                "original participant inventory required")
        position = self.ego.get_location()
        x0, y0 = self.site["route_xy"][0]
        x1, y1 = self.site["route_xy"][-1]
        norm = math.hypot(x1 - x0, y1 - y0)
        require(norm > 0, "reviewed route projection missing")
        direction = ((x1 - x0) / norm, (y1 - y0) / norm)
        vertices = self.ego.bounding_box.get_world_vertices(self.ego.get_transform())
        require(vertices, "original motorcycle front geometry missing")
        station = max(vertex.x * direction[0] + vertex.y * direction[1]
                      for vertex in vertices)
        require(math.isfinite(station), "invalid original motorcycle front geometry")
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        row = {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds,
               "source_kind": "native_world_snapshot",
               "official_head_id": self.site["official_head_id"],
               "facing_approach_id": self.site["ego_approach_id"],
               "actor_id": str(self.ego.id), "actor_type_id": self.ego.type_id,
               "lit_aspects": aspects.get("lit_aspects"),
               "ego_front_station_m": station, "speed_mps": speed,
               "other_users": users}
        self.index += 1
        return row

    def read_views(self, frame):
        require(len(self.queues) == 4, "four Native cameras not bound")
        result = {}
        for name in VIEWS:
            try:
                image = self.queues[name].get(timeout=10)
            except Empty as error:
                raise ValueError("original Native camera timeout: " + name) from error
            require(image.frame == frame, "original Native camera frame mismatch")
            result[name] = {"source_kind": "native_camera_sensor",
                            "sensor_id": str(self.sensors[name].id), "frame": image.frame,
                            "width": image.width, "height": image.height,
                            "bgra": bytes(image.raw_data)}
        return result

    def close(self):
        for name in reversed(VIEWS):
            sensor = self.sensors.pop(name, None)
            if sensor is not None:
                try:
                    sensor.stop()
                finally:
                    sensor.destroy()
        self.queues.clear()


@contextmanager
def open_session(case_id, site_path, host, port):
    """Open a 20 Hz world and restore its settings after the exact capture."""
    site_path = Path(site_path)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    require(site.get("case_id") == case_id and site.get("diagnostic_fixture") is False,
            "reviewed exact Native site required")
    verify_site(site, site_path.parent)
    observer = _load_observer(site, site_path.parent)
    import carla  # Lazy: CPU proof uses injected fake CARLA.
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    require(world.get_map().name == site["native_map_name"], "Native map differs")
    settings = world.get_settings()
    require(settings.synchronous_mode and math.isclose(settings.fixed_delta_seconds, 0.05,
                                                      abs_tol=1e-6),
            "reviewed 20 Hz synchronous Native world required")
    session = Session(world, carla, site, observer)
    try:
        yield session
    finally:
        session.close()
