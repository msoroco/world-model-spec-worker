"""CARLA adapter for an independently reviewed C157964 site packet.

This module imports CARLA only when an original attempt is requested. The site
packet must provide actor blueprints, camera poses and metric station axes;
diagnostic fixture coordinates cannot satisfy this source gate by accident.
"""

import io
import math
from queue import Empty, Queue

from yield_view import number, require


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def point(value, size):
    require(isinstance(value, list) and len(value) == size and all(number(v) for v in value),
            "reviewed metric point or pose missing")
    return value


def station(xy, origin, axis):
    return (xy[0] - origin[0]) * axis[0] + (xy[1] - origin[1]) * axis[1]


def corners(actor):
    transform = actor.get_transform()
    box = actor.bounding_box
    yaw = math.radians(transform.rotation.yaw)
    cosine, sine = math.cos(yaw), math.sin(yaw)
    offset = box.location
    vertices = []
    for dx in (-box.extent.x, box.extent.x):
        for dy in (-box.extent.y, box.extent.y):
            for dz in (-box.extent.z, box.extent.z):
                local_x, local_y = offset.x + dx, offset.y + dy
                vertices.append([transform.location.x + local_x * cosine - local_y * sine,
                                 transform.location.y + local_x * sine + local_y * cosine,
                                 transform.location.z + offset.z + dz])
    return vertices


def steering_to(location, yaw, target):
    desired = math.atan2(target[1] - location.y, target[0] - location.x)
    error = (desired - math.radians(yaw) + math.pi) % (2 * math.pi) - math.pi
    return max(-1.0, min(1.0, error / .7))


class Adapter:
    def __init__(self, config, host, port):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(20.0)
        self.world = self.client.get_world()
        self.config = config
        self.site = None
        self.case = None
        self.actors = {}
        self.sensors = {}
        self.queues = {}
        self.pending = {}
        self.routes = {}
        self.targets = {}
        self.reference_seen = False
        self.reference_hold = 0
        self.stop_released = False

    def provenance(self):
        return "original_native"

    def bind_site(self, site, case):
        require(self.site is None, "reviewed site already bound")
        blueprints = site.get("vehicle_blueprints")
        require(isinstance(blueprints, dict) and set(blueprints) == {"ego", "through"} and
                all(isinstance(v, str) and v.startswith("vehicle.") for v in blueprints.values()),
                "reviewed original vehicle blueprints missing")
        poses = site.get("camera_poses_xyzyaw")
        require(isinstance(poses, dict) and set(poses) == set(VIEWS),
                "reviewed original four camera poses missing")
        for pose in poses.values():
            point(pose, 4)
        for actor in ("ego", "through"):
            point(site.get(actor + "_spawn_pose_xyzyaw"), 4)
            route = site.get(actor + "_route_xy")
            require(isinstance(route, list) and len(route) >= 2,
                    "reviewed original participant route missing")
            for location in route:
                point(location, 2)
            point(site.get(actor + "_station_origin_xy"), 2)
            axis = point(site.get(actor + "_station_axis_xy"), 2)
            require(abs(math.hypot(*axis) - 1) < .001, "reviewed station axis must be unit length")
        require(site["ego_route_xy"] == site["route_xy"] and
                site["ego_spawn_pose_xyzyaw"][:2] == site["route_xy"][0] and
                site["through_spawn_pose_xyzyaw"][:2] == site["through_spawn_xy"],
                "reviewed original routes disagree with selected construction")
        if case.officer_controls:
            officer = site.get("officer_actor")
            require(isinstance(officer, dict) and isinstance(officer.get("blueprint_id"), str) and
                    officer["blueprint_id"].startswith("walker.") and
                    point(officer.get("pose_xyzyaw"), 4),
                    "reviewed original officer actor missing")
        require(isinstance(site.get("sight_observation"), dict) and
                bool(site["sight_observation"]), "reviewed sight observation missing")
        entry = site.get("through_intersection_entry_station_m")
        exit_station = site.get("through_intersection_exit_station_m")
        require(number(entry) and number(exit_station) and entry < exit_station,
                "reviewed through intersection limits missing")
        fov = site.get("camera_fov_deg")
        require(isinstance(fov, dict) and set(fov) == set(VIEWS) and
                all(number(v) and 20 <= v <= 150 for v in fov.values()),
                "reviewed original camera fields of view missing")
        self.site, self.case = site, case

    def pose(self, values):
        x, y, z, yaw = point(values, 4)
        return self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                    self.carla.Rotation(yaw=yaw))

    def blueprint(self, blueprint_id):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        require(blueprint is not None and blueprint.id == blueprint_id,
                "reviewed actor blueprint unavailable")
        return blueprint

    def spawn_checked(self, blueprint, pose, label):
        actor = self.world.try_spawn_actor(blueprint, pose)
        if actor is None:
            raise ValueError("reviewed original " + label + " spawn failed")
        if self.world.get_actor(actor.id) is None:
            actor.destroy()
            raise ValueError("reviewed original " + label + " readback failed")
        return actor

    def snapshot_settings(self):
        return self.world.get_settings()

    def set_synchronous(self, delta):
        require(self.site is not None, "reviewed site not bound")
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = delta
        self.world.apply_settings(settings)

    def spawn_vehicle(self, xy, role):
        require(role in ("ego", "through") and role not in self.actors and
                xy == self.site[role + "_spawn_pose_xyzyaw"][:2],
                "selected participant spawn differs from reviewed pose")
        actor = self.spawn_checked(
            self.blueprint(self.site["vehicle_blueprints"][role]),
            self.pose(self.site[role + "_spawn_pose_xyzyaw"]), "vehicle")
        self.actors[role] = actor
        return actor

    def set_yield_approach(self, ego, route, reference, policy):
        require(ego is self.actors["ego"] and route == self.site["ego_route_xy"] and
                reference == self.site["nearest_view_station_m"] and
                policy in ("slow", "stop"), "selected yield approach differs")
        self.routes["ego"] = route
        self.targets["ego"] = 1
        self.policy = policy

    def set_through_phase(self, through, phase):
        require(through is self.actors["through"] and phase in ("approaching", "occupied") and
                phase == self.case.through_state, "selected through phase differs")
        self.routes["through"] = self.site["through_route_xy"]
        self.targets["through"] = 1
        self.phase = phase

    def set_officer_control(self, enabled):
        require(enabled is self.case.officer_controls, "selected officer context differs")
        self.officer = None
        if enabled:
            specification = self.site["officer_actor"]
            actor = self.spawn_checked(self.blueprint(specification["blueprint_id"]),
                                       self.pose(specification["pose_xyzyaw"]), "officer")
            self.officer = actor

    def start_cameras(self, owned, views, dimensions):
        require(tuple(views) == VIEWS and dimensions == self.site["camera_dimensions"] and
                tuple(owned) == (self.actors["ego"], self.actors["through"]),
                "selected original camera/participant setup differs")
        for view in VIEWS:
            blueprint = self.blueprint("sensor.camera.rgb")
            width, height = dimensions[view]
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            blueprint.set_attribute("fov", str(self.site["camera_fov_deg"][view]))
            sensor = self.spawn_checked(blueprint,
                                        self.pose(self.site["camera_poses_xyzyaw"][view]),
                                        "camera")
            queue = Queue()
            sensor.listen(queue.put)
            self.sensors[view], self.queues[view], self.pending[view] = sensor, queue, {}

    def _drive(self, role):
        actor = self.actors[role]
        pose = actor.get_transform()
        route = self.routes[role]
        index = self.targets[role]
        target = route[index]
        distance = math.dist((pose.location.x, pose.location.y), target)
        if distance < 1.5 and index < len(route) - 1:
            index += 1
            self.targets[role] = index
            target = route[index]
        speed = math.hypot(actor.get_velocity().x, actor.get_velocity().y)
        desired = 6.0 if role == "through" else 4.0
        if role == "ego" and not self.reference_seen:
            leading = max(station(vertex, self.site["ego_station_origin_xy"],
                                  self.site["ego_station_axis_xy"]) for vertex in corners(actor))
            gap = self.site["nearest_view_station_m"] - leading
            if gap < 5 and self.policy == "slow":
                desired = 2.0
            elif gap < 5 and self.policy == "stop" and not self.stop_released:
                desired = 0.0
            if self.policy == "stop" and not self.stop_released and gap < 2 and speed < .12:
                self.reference_hold += 1
            if self.reference_hold >= 20:
                self.stop_released = True
        finished = index == len(route) - 1 and distance < 1.0
        throttle = 0.0 if finished or speed > desired else .35
        brake = 1.0 if finished or speed > desired + .4 else 0.0
        actor.apply_control(self.carla.VehicleControl(
            throttle=throttle, brake=brake,
            steer=steering_to(pose.location, pose.rotation.yaw, target)))

    def tick(self):
        for role in ("ego", "through"):
            self._drive(role)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        require(snapshot.frame == frame, "original world snapshot frame differs")
        return {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds}

    def observe(self, owned, snapshot):
        require(tuple(owned) == (self.actors["ego"], self.actors["through"]),
                "original participant identity differs")
        for actor in owned:
            require(actor.is_alive and self.world.get_actor(actor.id) is not None,
                    "original participant disappeared")
        ego, through = owned
        e_vertices, t_vertices = corners(ego), corners(through)
        e_stations = [station(v, self.site["ego_station_origin_xy"],
                              self.site["ego_station_axis_xy"]) for v in e_vertices]
        t_stations = [station(v, self.site["through_station_origin_xy"],
                              self.site["through_station_axis_xy"]) for v in t_vertices]
        entry = self.site["through_intersection_entry_station_m"]
        exit_station = self.site["through_intersection_exit_station_m"]
        observed_phase = ("approaching" if max(t_stations) < entry else
                          "occupied" if min(t_stations) <= exit_station else "departed")
        t_pose = through.get_transform().location
        ego_leading = max(e_stations)
        at_reference = not self.reference_seen and ego_leading >= self.site["nearest_view_station_m"]
        if at_reference:
            self.reference_seen = True
        officer_id = None
        if self.case.officer_controls:
            require(self.officer is not None and self.officer.is_alive and
                    self.world.get_actor(self.officer.id) is not None,
                    "original officer readback missing")
            officer_id = str(self.officer.id)
        velocity = ego.get_velocity()
        return {"ego_id": str(ego.id), "through_id": str(through.id),
                "ego_speed_mps": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                "ego_leading_station_m": ego_leading,
                "through_center_station_m": station([t_pose.x, t_pose.y],
                                                    self.site["through_station_origin_xy"],
                                                    self.site["through_station_axis_xy"]),
                "through_min_vertex_station_m": min(t_stations),
                "through_phase": observed_phase,
                "ego_across_or_within": ego_leading >= self.site["physical_reference_station_m"],
                "officer_controls": self.case.officer_controls,
                "signal_controls": False,
                "stop_line_present": False, "near_crosswalk_present": False,
                "sight_observation": {"reviewed_source_sha256": self.site["sight_observation_source_sha256"],
                                      "reviewed_record": self.site["sight_observation"]},
                "body_vertices": {"ego": e_vertices, "through": t_vertices},
                "control_readback": {"officer_directing_traffic": self.case.officer_controls,
                                     "traffic_signal_controlling": False,
                                     "officer_actor_id": officer_id},
                "all_at_reference_observed": at_reference}

    def camera_packets(self, snapshot):
        from PIL import Image
        packets = {}
        for view in VIEWS:
            image = self.pending[view].pop(snapshot["frame"], None)
            while image is None:
                try:
                    candidate = self.queues[view].get(timeout=10.0)
                except Empty as exc:
                    raise ValueError("original camera packet timed out") from exc
                if candidate.frame == snapshot["frame"]:
                    image = candidate
                elif candidate.frame > snapshot["frame"]:
                    self.pending[view][candidate.frame] = candidate
                else:
                    raise ValueError("stale original camera packet")
            rgba = Image.frombytes("RGBA", (image.width, image.height),
                                   bytes(image.raw_data), "raw", "BGRA")
            stream = io.BytesIO()
            rgba.convert("RGB").save(stream, format="PNG")
            packets[view] = {"frame": image.frame, "time_s": image.timestamp,
                             "width": image.width, "height": image.height,
                             "sensor_id": str(self.sensors[view].id), "png": stream.getvalue()}
        return packets

    def stop_cameras(self):
        error = None
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except Exception as exc:
                error = error or exc
            finally:
                try:
                    sensor.destroy()
                except Exception as exc:
                    error = error or exc
        self.sensors.clear()
        if error is not None:
            raise error

    def destroy(self, actor):
        actor.destroy()

    def restore_settings(self, settings):
        try:
            if self.sensors:
                self.stop_cameras()
        finally:
            try:
                if self.officer is not None:
                    self.officer.destroy()
            finally:
                self.world.apply_settings(settings)


def create_adapter(config, host, port):
    return Adapter(config, host, port)
