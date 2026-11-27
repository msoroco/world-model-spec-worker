"""CARLA-lazy source-gated operator for the C158190 yield variant.

The immutable catalog still describes a stop-sign cell. A local capture needs a
separately reviewed yield site and actual map/actor readback before this operator
can run. No synthetic packet is physical evidence.
"""

from __future__ import annotations

import hashlib
import math
import queue


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite reviewed " + name + " required")
    return float(value)


def validate_scene(site):
    scene = site.get("native_scene")
    if not isinstance(scene, dict):
        raise ValueError("reviewed Native scene source required")
    for name in ("ego", "through_vehicle"):
        actor = scene.get(name)
        if not isinstance(actor, dict) or not isinstance(actor.get("blueprint_id"), str) or not actor["blueprint_id"].startswith("vehicle."):
            raise ValueError("reviewed " + name + " vehicle blueprint required")
        pose(actor.get("transform"))
    cams = scene.get("cameras")
    if not isinstance(cams, dict) or set(cams) != set(VIEWS):
        raise ValueError("four reviewed camera transforms required")
    for name in VIEWS:
        cam = cams[name]
        if not isinstance(cam, dict) or cam.get("attach_to") not in ("ego", "through_vehicle"):
            raise ValueError("reviewed camera parent required: " + name)
        pose(cam.get("transform"))
        fov = finite(cam.get("fov_deg"), name + " fov")
        if not 0 < fov < 180:
            raise ValueError("physical camera fov required")
    polygon = scene.get("intersection_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("reviewed intersection polygon required")
    for point in polygon:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("reviewed intersection vertex required")
        finite(point[0], "intersection x")
        finite(point[1], "intersection y")
    conflict = scene.get("through_conflict_point_xy_m")
    if not isinstance(conflict, list) or len(conflict) != 2:
        raise ValueError("reviewed through conflict point required")
    finite(conflict[0], "through conflict x")
    finite(conflict[1], "through conflict y")
    stations = scene.get("approach_view_stations")
    if not isinstance(stations, list) or len(stations) < 2:
        raise ValueError("reviewed approach view station sequence required")
    for station in stations:
        if not isinstance(station, dict) or not station.get("station_id"):
            raise ValueError("reviewed view station identity required")
        for key in ("x", "y", "z", "distance_to_intersection_m"):
            finite(station.get(key), "view station " + key)
    for key in ("brake_distance_m", "slow_speed_mps", "through_speed_mps"):
        if finite(scene.get(key), key) < 0:
            raise ValueError("nonnegative reviewed controller setting required")
    return scene


def pose(data):
    if not isinstance(data, dict):
        raise ValueError("reviewed Native transform required")
    for key in ("x", "y", "z", "yaw"):
        finite(data.get(key), "transform " + key)
    for key in ("pitch", "roll"):
        finite(data.get(key, 0), "transform " + key)
    return data


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def _speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def _body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(points) != 8:
        raise ValueError("original vehicle body must have eight vertices")
    return [_xyz(point) for point in points]


class CarlaYieldOperator:
    def __init__(self, world, site, case_id, carla):
        self.world, self.site, self.case_id, self.carla = world, site, case_id, carla
        self.scene = validate_scene(site)
        self.ego = self.through = self.sign = None
        self.cameras = {}
        self.inboxes = {}

    def _transform(self, data):
        source = pose(data)
        return self.carla.Transform(
            self.carla.Location(x=source["x"], y=source["y"], z=source["z"]),
            self.carla.Rotation(yaw=source["yaw"], pitch=source.get("pitch", 0),
                                roll=source.get("roll", 0)))

    def _spawn(self, blueprint_id, transform, **kwargs):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.spawn_actor(blueprint, self._transform(transform), **kwargs)
        if actor is None:
            raise ValueError("Native actor spawn failed: " + blueprint_id)
        return actor

    def map_bytes(self, world):
        if world is not self.world:
            raise ValueError("Native world ownership differs")
        raw = world.get_map().to_opendrive().encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != self.site["map_source_sha256"]:
            raise ValueError("reviewed OpenDRIVE source differs from Native world")
        return raw

    def read_control(self, approach):
        if approach != self.site["yield_sign"]["governed_approach_id"]:
            raise ValueError("governed approach identity differs")
        self.map_bytes(self.world)
        sign = self.site["yield_sign"]["transform"]
        for landmark in self.world.get_map().get_all_landmarks():
            kind = str(getattr(landmark, "type", "")).lower()
            if kind not in ("206", "stop", "205", "yield"):
                continue
            location = landmark.transform.location
            if math.hypot(location.x - sign["x"], location.y - sign["y"]) < 12:
                return "stop_sign" if kind in ("206", "stop") else "yield_sign"
        for actor in self.world.get_actors():
            kind = str(getattr(actor, "type_id", "")).lower()
            if "stop" not in kind and "yield" not in kind:
                continue
            location = actor.get_transform().location
            if math.hypot(location.x - sign["x"], location.y - sign["y"]) < 12:
                return "stop_sign" if "stop" in kind else "yield_sign"
        return None

    def spawn_yield_sign(self, blueprint_id, transform):
        if "yield" not in blueprint_id.lower():
            raise ValueError("reviewed yield blueprint differs")
        self.sign = self._spawn(blueprint_id, transform)
        return self.sign.id

    def read_sign(self, sign_id):
        actor = self.world.get_actor(sign_id)
        if actor is None or self.sign is None or actor.id != self.sign.id or "yield" not in actor.type_id.lower():
            raise ValueError("Native yield-sign actor readback differs")
        expected = self.site["yield_sign"]["transform"]
        location = actor.get_transform().location
        if math.hypot(location.x - expected["x"], location.y - expected["y"]) > 0.5:
            raise ValueError("Native yield-sign location differs")
        return {"control": "yield_sign", "governed_approach_id":
                self.site["yield_sign"]["governed_approach_id"], "actor_id": actor.id}

    def survey_markings(self, approach):
        self.read_control(approach)
        # CARLA does not expose a complete crosswalk/sidewalk API. The reviewed
        # source survey is held fixed by the current OpenDRIVE byte seal.
        return {name: self.site[name] for name in
                ("stop_line_present", "near_crosswalk_present",
                 "sidewalk_derived_crosswalk_present")}

    def survey_view_stations(self, approach):
        self.read_control(approach)
        if self.through is None:
            # The first site survey happens before the through actor is spawned.
            # Visibility is evaluated again from original frames after spawn.
            return [{"station_id": station["station_id"],
                     "distance_to_intersection_m": station["distance_to_intersection_m"],
                     "view_of_through_traffic": station.get("reviewed_visible") is True}
                    for station in self.scene["approach_view_stations"]]
        return self._view_stations()

    def _view_stations(self):
        target = self.through.get_transform().location
        rows = []
        for station in self.scene["approach_view_stations"]:
            origin = self.carla.Location(x=station["x"], y=station["y"], z=station["z"])
            hits = self.world.cast_ray(origin, target)
            if hits is None:
                raise ValueError("Native nearest-view raycast unavailable")
            ids = [getattr(hit, "actor_id", None) for hit in hits]
            rows.append({"station_id": station["station_id"],
                         "distance_to_intersection_m": station["distance_to_intersection_m"],
                         "view_of_through_traffic": not ids or ids[0] == self.through.id})
        return rows

    def spawn_through_vehicle(self, plan, delay):
        if plan.get("route_source_id") != self.site["through_vehicle"]["route_source_id"]:
            raise ValueError("reviewed through route changed")
        owned = []
        try:
            self.ego = self._spawn(self.scene["ego"]["blueprint_id"], self.scene["ego"]["transform"])
            owned.append(self.ego)
            self.through = self._spawn(self.scene["through_vehicle"]["blueprint_id"],
                                       self.scene["through_vehicle"]["transform"])
            owned.append(self.through)
            for view in VIEWS:
                source = self.scene["cameras"][view]
                blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
                width, height = SIZES[view]
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", str(source["fov_deg"]))
                parent = self.ego if source["attach_to"] == "ego" else self.through
                sensor = self.world.spawn_actor(blueprint, self._transform(source["transform"]), attach_to=parent)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + view)
                owned.append(sensor)
                inbox = queue.Queue(maxsize=2)
                sensor.listen(inbox.put)
                self.cameras[view], self.inboxes[view] = sensor, inbox
            return self.through.id
        except BaseException:
            for actor in reversed(owned):
                actor.destroy()
            self.cameras.clear()
            self.inboxes.clear()
            self.ego = self.through = None
            raise

    def destroy(self, actor_id):
        if self.through is not None and actor_id == self.through.id:
            for sensor in reversed(list(self.cameras.values())):
                sensor.stop()
                sensor.destroy()
            self.cameras.clear()
            self.inboxes.clear()
            self.ego.destroy()
            self.through.destroy()
            self.ego = self.through = None
        elif self.sign is not None and actor_id == self.sign.id:
            self.sign.destroy()
            self.sign = None
        else:
            raise ValueError("unowned Native actor release requested")

    def read_original_context(self, site, case_id):
        if site is not self.site or case_id != self.case_id or self.through is None:
            raise ValueError("Native original context owner differs")
        self.map_bytes(self.world)
        return {"assignment_id": site["assignment_id"], "case_id": case_id,
                "source_kind": "original_native_readback",
                "source_recording_id": site["intersection_id"] + ":" + str(self.ego.id),
                "intersection_id": site["intersection_id"], "control": "yield_sign",
                "stop_line_present": site["stop_line_present"],
                "near_crosswalk_present": site["near_crosswalk_present"],
                "sidewalk_derived_crosswalk_present": site["sidewalk_derived_crosswalk_present"],
                "police_control_active": site["police_control_active"],
                "traffic_signal_control_active": site["traffic_signal_control_active"],
                "approach_view_stations": self._view_stations(),
                **{key: site[key] for key in ("map_source_sha256", "ego_route_source_sha256",
                   "yield_sign_survey_sha256", "marking_survey_sha256",
                   "view_ray_survey_sha256", "through_highway_survey_sha256")}}

    def control_frame(self, case_id, index):
        if case_id != self.case_id or self.ego is None or self.through is None:
            raise ValueError("Native controller ownership differs")
        plan = self.site["case_plans"][case_id.rsplit("__", 1)[-1]]
        speed = _speed(self.ego)
        target = self.scene["slow_speed_mps"]
        if plan["ego_response"] == "stop":
            anchor = self.scene["approach_view_stations"][-1]
            position = self.ego.get_transform().location
            if math.hypot(position.x - anchor["x"], position.y - anchor["y"]) <= self.scene["brake_distance_m"]:
                target = 0.0
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=0.35 if speed < target - 0.3 else 0.0,
            brake=0.6 if speed > target + 0.3 else 0.0))
        through_target = self.scene["through_speed_mps"] if index / 20 >= plan["through_start_delay_s"] else 0.0
        through_speed = _speed(self.through)
        self.through.apply_control(self.carla.VehicleControl(
            throttle=0.35 if through_speed < through_target - 0.3 else 0.0,
            brake=0.6 if through_speed > through_target + 0.3 else 0.0))

    def read_original_frame(self, case_id, index, native_frame):
        if case_id != self.case_id or self.ego is None or self.through is None:
            raise ValueError("Native frame owner differs")
        from shapely.geometry import MultiPoint, Point, Polygon
        polygon = Polygon(self.scene["intersection_polygon_xy_m"])
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError("reviewed intersection geometry invalid")
        ego_body = _body(self.ego)
        ego = self.ego.get_transform().location
        through = self.through.get_transform().location
        footprint = MultiPoint([vertex[:2] for vertex in ego_body]).convex_hull
        if not isinstance(footprint, Polygon) or footprint.area <= 0:
            raise ValueError("original ego body footprint invalid")
        through_speed = _speed(self.through)
        conflict_x, conflict_y = self.scene["through_conflict_point_xy_m"]
        return {"case_id": case_id, "frame": index, "native_frame": native_frame,
                "original_frame": native_frame, "time_s": index / 20,
                "actor_id": self.ego.id, "vehicle_blueprint": self.ego.type_id,
                "position_m": _xyz(ego),
                "heading_xy": [math.cos(math.radians(self.ego.get_transform().rotation.yaw)),
                               math.sin(math.radians(self.ego.get_transform().rotation.yaw))],
                "body_vertices_m": ego_body, "ego_speed_mps": _speed(self.ego),
                "ego_within_intersection": polygon.intersects(footprint),
                "distance_to_intersection_m": Point(ego.x, ego.y).distance(polygon),
                "through_vehicle_ids": [str(self.through.id)],
                "through_vehicles": [{"id": str(self.through.id), "through_highway": True,
                                      "distance_to_conflict_m": math.hypot(through.x - conflict_x,
                                                                          through.y - conflict_y),
                                      "speed_mps": through_speed}],
                "control": "yield_sign", "stop_line_present": False,
                "near_crosswalk_present": False,
                **{key: self.site[key] for key in ("map_source_sha256", "ego_route_source_sha256",
                   "yield_sign_survey_sha256", "marking_survey_sha256",
                   "view_ray_survey_sha256", "through_highway_survey_sha256")}}

    def camera_rgb24(self, view, native_frame):
        if view not in self.inboxes:
            raise ValueError("unowned original camera view")
        try:
            image = self.inboxes[view].get(timeout=5)
        except queue.Empty as error:
            raise ValueError("original camera frame missing: " + view) from error
        width, height = SIZES[view]
        if image.frame != native_frame or image.width != width or image.height != height:
            raise ValueError("original camera frame join or dimensions differ: " + view)
        from PIL import Image
        data = bytes(image.raw_data)
        if len(data) != width * height * 4:
            raise ValueError("original BGRA frame length differs: " + view)
        return Image.frombytes("RGBA", (width, height), data, "raw", "BGRA").convert("RGB").tobytes()


def make_adapter(world, site, case_id):
    import carla
    return CarlaYieldOperator(world, site, case_id, carla)
