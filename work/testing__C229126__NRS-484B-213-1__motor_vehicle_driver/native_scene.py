"""Reviewed-source CARLA construction for exact left-of-center passing cases.

All CARLA imports occur during an explicit live construction. Packet coordinates are
reviewed Native facts, not inferred legal findings or fixture-ready road claims.
"""
from __future__ import annotations

import hashlib
import math

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
ASSIGNMENT = "testing__C229126__NRS-484B-213-1__motor_vehicle_driver"
CASE_VARIANTS = {"clear_free_complete", "occluded_left", "oncoming_distant",
                 "oncoming_close", "opposite_response", "overtaken_response",
                 "incomplete_pass"}


def require(value, message):
    if not value:
        raise ValueError(message)


def vector(values, length, label):
    require(isinstance(values, list) and len(values) == length and
            all(type(v) in (float, int) and math.isfinite(v) for v in values),
            "reviewed " + label + " coordinates required")
    return values


def validate(packet, case_id):
    require(case_id.startswith(ASSIGNMENT + "__") and
            case_id.split("__")[-1] in CASE_VARIANTS and packet.get("case_id") == case_id,
            "exact pass case mismatch")
    require(packet.get("law_id") == "NRS-484B-213-1" and
            packet.get("cell_id") == "C229126" and
            packet.get("actor") == "motor_vehicle_driver", "scope mismatch")
    require(packet.get("reviewed") is True and packet.get("reviewer") and
            packet.get("review_source_sha256"), "separate original road review required")
    require(packet.get("map_opendrive_sha256") and packet.get("road", {}).get("public_highway") is True,
            "reviewed original public highway required")
    require(packet.get("fps") == 20 and type(packet.get("duration_s")) is int and
            packet["duration_s"] >= 20, "20 Hz complete pass duration required")
    road = packet["road"]
    require(road.get("lane_count") == 2 and road.get("opposite_permitted_directions") is True and
            road.get("undivided") is True and road.get("centerline_source_sha256"),
            "reviewed two-way two-lane centerline required")
    lanes = road.get("lanes")
    require(isinstance(lanes, list) and len(lanes) == 2 and
            {lane.get("direction") for lane in lanes} == {1, -1} and
            all(lane.get("lane_id") for lane in lanes), "both original lane directions required")
    axis = vector(road.get("forward_unit_xy"), 2, "reviewed forward lane axis")
    require(abs(math.hypot(*axis)-1) <= .01, "reviewed forward lane axis not unit length")
    vector(road.get("centerline_origin_xy"), 2, "reviewed centerline origin")
    actors = packet.get("actors")
    require(isinstance(actors, dict) and {"ego", "overtaken"} <= set(actors),
            "ego and overtaken vehicles required")
    for name, item in actors.items():
        require(name in ("ego", "overtaken", "oncoming"), "unknown actor role")
        require(str(item.get("blueprint", "")).startswith("vehicle."),
                "reviewed vehicle blueprint required")
        vector(item.get("pose"), 6, name + " pose")
        route = item.get("route")
        require(isinstance(route, list) and len(route) >= 2,
                "reviewed actor route required")
        for point in route:
            vector(point, 3, name + " route")
        projected = ((route[-1][0]-route[0][0])*axis[0] +
                     (route[-1][1]-route[0][1])*axis[1])
        require(projected*item.get("direction", 0) > 5,
                "reviewed actor route contradicts permitted lane direction: " + name)
        heading = math.radians(item["pose"][4])
        alignment = ((route[-1][0]-route[0][0])*math.cos(heading) +
                     (route[-1][1]-route[0][1])*math.sin(heading))
        require(alignment > 5, "reviewed actor initial heading contradicts route: " + name)
        require(type(item.get("target_speed_mps")) in (float, int) and
                0 < item["target_speed_mps"] < 50 and item.get("source_sha256"),
                "reviewed actor speed/source required")
        response = item.get("response_policy")
        if response is not None:
            require(name in ("oncoming", "overtaken") and
                    type(response.get("start_frame")) is int and
                    0 <= response["start_frame"] < 20*packet.get("duration_s", 0) and
                    type(response.get("target_speed_mps")) in (int, float) and
                    0 <= response["target_speed_mps"] < 50 and
                    response.get("source_sha256"),
                    "reviewed response policy required")
    require(actors["ego"].get("direction") == actors["overtaken"].get("direction") == 1,
            "passing actors must share reviewed travel direction")
    if "oncoming" in actors:
        require(actors["oncoming"].get("direction") == -1,
                "oncoming actor must travel on opposite permitted lane")
    if case_id.endswith(("oncoming_distant", "oncoming_close", "opposite_response")):
        require("oncoming" in actors, "oncoming comparison requires original actor")
    if case_id.endswith("occluded_left"):
        blocker = packet.get("opaque_blocker")
        require(isinstance(blocker, dict) and blocker.get("blueprint") and
                blocker.get("source_sha256") and blocker.get("ray_intersection_plan"),
                "physical opaque blocker required")
        vector(blocker.get("pose"), 6, "opaque blocker pose")
    if case_id.endswith("opposite_response"):
        require(actors["oncoming"].get("response_policy"), "opposite response controller required")
    if case_id.endswith("overtaken_response"):
        require(actors["overtaken"].get("response_policy"), "overtaken response controller required")
    cameras = packet.get("cameras")
    require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
            "four reviewed camera poses required")
    for name, size in zip(CAMERAS, CAMERA_SIZES):
        camera = cameras[name]
        vector(camera.get("pose"), 6, name + " camera pose")
        require((camera.get("width"), camera.get("height")) == size and
                type(camera.get("fov_deg")) in (float, int) and
                1 <= camera["fov_deg"] <= 170, "pinned four-view profile required")
    return packet


def transform(carla, values):
    x, y, z, pitch, yaw, roll = vector(values, 6, "Native pose")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


class PassScene:
    """Owns all new actors/sensors; the operator provides an exclusive client."""

    def __init__(self, client, packet, case_id, source_root, *, carla_module=None,
                 snapshot_fn=None, restore_fn=None, bind_fn=None):
        self.client = client
        self.packet = validate(packet, case_id)
        self.case_id = case_id
        self.carla = carla_module
        self.source_root = source_root
        self.bind_fn = bind_fn
        self.snapshot_fn = snapshot_fn
        self.restore_fn = restore_fn
        self.saved = None
        self.world = None
        self.actors = {}
        self.sensors = {}
        self.closed = False
        self.release = None
        self.route_indices = {role: 0 for role in self.packet["actors"]}
        self.last_world_frame = None

    def begin(self):
        if self.bind_fn is None:
            from source_bind import bind
            self.bind_fn = bind
        self.bound_sources = self.bind_fn(self.packet, self.source_root)
        if self.carla is None:
            import carla
            self.carla = carla
        if self.snapshot_fn is None or self.restore_fn is None:
            from worker_exchange.world_restore import snapshot, restore
            self.snapshot_fn, self.restore_fn = snapshot, restore
        self.saved = self.snapshot_fn(self.client)
        try:
            self.world = self.client.get_world()
            actual = hashlib.sha256(self.world.get_map().to_opendrive().encode()).hexdigest()
            require(actual == self.packet["map_opendrive_sha256"],
                    "live OpenDRIVE differs from reviewed original source")
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = .05
            self.world.apply_settings(settings)
            library = self.world.get_blueprint_library()
            for role, item in self.packet["actors"].items():
                actor = self.world.try_spawn_actor(library.find(item["blueprint"]),
                                                   transform(self.carla, item["pose"]))
                require(actor is not None, "reviewed vehicle spawn failed: " + role)
                self.actors[role] = actor
            if self.case_id.endswith("occluded_left"):
                blocker = self.packet["opaque_blocker"]
                actor = self.world.try_spawn_actor(library.find(blocker["blueprint"]),
                                                   transform(self.carla, blocker["pose"]))
                require(actor is not None, "opaque blocker spawn failed")
                self.actors["opaque_blocker"] = actor
            for name in CAMERAS:
                item = self.packet["cameras"][name]
                blueprint = library.find("sensor.camera.rgb")
                for key, value in (("image_size_x", item["width"]),
                                   ("image_size_y", item["height"]),
                                   ("fov", item["fov_deg"]), ("sensor_tick", .05)):
                    blueprint.set_attribute(key, str(value))
                sensor = self.world.spawn_actor(blueprint, transform(self.carla, item["pose"]))
                require(sensor is not None, "reviewed camera spawn failed: " + name)
                self.sensors[name] = sensor
            return {"case_id": self.case_id, "map_opendrive_sha256": actual,
                    "actor_roles": sorted(self.actors), "cameras": list(CAMERAS),
                    "physical_completion_claimed": False}
        except BaseException:
            self.close()
            raise

    def _apply_route(self, role, episode_frame):
        actor = self.actors[role]
        spec = self.packet["actors"][role]
        route = spec["route"]
        location = actor.get_location()
        index = self.route_indices[role]
        while index < len(route) - 1 and math.hypot(route[index][0]-location.x,
                                                     route[index][1]-location.y) < 2:
            index += 1
        self.route_indices[role] = index
        target = route[index]
        distance = math.hypot(target[0]-location.x, target[1]-location.y)
        if index == len(route)-1 and distance < 2:
            control = self.carla.VehicleControl(throttle=0, brake=1, steer=0)
            actor.apply_control(control)
            return {"role": role, "route_index": index, "target_speed_mps": 0,
                    "controller_stopped": True}
        transform = actor.get_transform()
        yaw = math.radians(transform.rotation.yaw)
        heading = math.atan2(target[1]-location.y, target[0]-location.x)
        error = math.atan2(math.sin(heading-yaw), math.cos(heading-yaw))
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        requested = spec["target_speed_mps"]
        response = spec.get("response_policy")
        if response and episode_frame >= response["start_frame"]:
            requested = response["target_speed_mps"]
        throttle = max(0.0, min(0.65, 0.20*(requested-speed)))
        brake = max(0.0, min(0.7, 0.25*(speed-requested)))
        steer = max(-0.65, min(0.65, 1.5*error))
        actor.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake,
                                                       steer=steer))
        return {"role": role, "route_index": index, "target_speed_mps": requested,
                "observed_speed_mps": speed, "requested_steer": steer,
                "controller_stopped": False}

    def tick(self, episode_frame):
        require(self.world is not None and not self.closed, "Native scene not active")
        commands = [self._apply_route(role, episode_frame) for role in self.packet["actors"]]
        world_frame = self.world.tick()
        require(type(world_frame) is int and
                (self.last_world_frame is None or world_frame == self.last_world_frame+1),
                "original CARLA world frame discontinuity")
        self.last_world_frame = world_frame
        return {"world_frame": world_frame, "commands": commands}

    def close(self):
        if self.closed:
            return self.release
        errors = []
        for sensor in reversed(list(self.sensors.values())):
            for operation in (sensor.stop, sensor.destroy):
                try:
                    operation()
                except Exception as exc:
                    errors.append(str(exc))
        for actor in reversed(list(self.actors.values())):
            try:
                actor.destroy()
            except Exception as exc:
                errors.append(str(exc))
        restored = None
        if self.saved is not None:
            try:
                restored = self.restore_fn(self.client, self.saved)
            except Exception as exc:
                errors.append(str(exc))
        self.release = {"actors_released": not errors, "sensors_released": not errors,
                        "world_restored": bool(restored and restored.get("restored")),
                        "restoration": restored, "errors": errors}
        self.closed = True
        require((self.release["world_restored"] or self.saved is None) and not errors,
                "release or restoration readback failed: " + "; ".join(errors))
        return self.release
