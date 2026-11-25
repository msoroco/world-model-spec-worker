"""Source-gated CARLA construction for the six NRS 484B.257(2) cases.

The local operator supplies a reviewed site survey. Survey values select Native
objects; they never substitute for Native readback. No CARLA import occurs here.
"""
from __future__ import annotations

import hashlib
import json
from math import hypot, isfinite
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(root, item):
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("original source reference is incomplete")
    name = item["path"]
    if not isinstance(name, str) or not name or Path(name).is_absolute() or Path(name).name != name:
        raise ValueError("original source must be a direct child of site bundle")
    path = root / name
    if not path.is_file() or _sha(path) != item["sha256"]:
        raise ValueError("original source missing or changed: " + name)
    return path


def _finite(value, name):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("nonfinite " + name)
    return float(value)


def _pose(value, name):
    if not isinstance(value, dict) or set(value) != {"x", "y", "z", "yaw"}:
        raise ValueError("source-surveyed transform missing: " + name)
    return {key: _finite(value[key], name + "." + key) for key in value}


def load_site(bundle, case_id, control_context):
    """Validate immutable survey inventory before connecting to CARLA."""
    root = Path(bundle).resolve()
    index = json.loads((root / "bundle-index.json").read_text())
    if (index.get("format") != "c158196-original-site-bundle" or
            index.get("cell_id") != "C158196" or
            index.get("case_id") != case_id or
            index.get("control_context") != control_context):
        raise ValueError("original site bundle does not match exact case")
    refs = index.get("sources")
    if not isinstance(refs, list) or len(refs) < 3:
        raise ValueError("original map/device/route sources missing")
    paths = {item.get("path") for item in refs if isinstance(item, dict)}
    if paths != {"site.json", "devices.json", "routes.json"}:
        raise ValueError("unexpected original site source inventory")
    docs = {item["path"]: json.loads(_source(root, item).read_text()) for item in refs}
    site, devices, routes = docs["site.json"], docs["devices.json"], docs["routes.json"]
    if (site.get("cell_id") != "C158196" or
            site.get("layout") != "one_way_to_two_way_intersection" or
            site.get("through_highway") is not False or
            not isinstance(site.get("native_map_name"), str) or
            not site["native_map_name"]):
        raise ValueError("reviewed site cannot establish non-through intersection")
    bounds = site.get("intersection_rectangle_xy")
    if (not isinstance(bounds, list) or len(bounds) != 4 or
            not all(type(x) in (int, float) and isfinite(x) for x in bounds) or
            not bounds[0] < bounds[2] or not bounds[1] < bounds[3]):
        raise ValueError("reviewed intersection bounds missing")
    if (devices.get("case_id") != case_id or
            devices.get("control_context") != control_context or
            not isinstance(devices.get("ego_control_actor_id"), int) or
            devices.get("facing_road_id") != routes.get("ego_approach", {}).get("road_id") or
            devices.get("facing_lane_id") != routes.get("ego_approach", {}).get("lane_id") or
            not isinstance(devices.get("counterpart_priority_source"), dict)):
        raise ValueError("original controlling authority inventory missing")
    if control_context in {"stop_sign", "yield_sign"}:
        if (devices.get("sign_kind") != control_context or
                devices.get("signal_controlling") is not False or
                devices.get("officer_controlling") is not False):
            raise ValueError("sign branch lacks independent controlling sign")
    elif control_context == "signal_exception":
        if devices.get("signal_controlling") is not True:
            raise ValueError("signal exception source missing")
    elif control_context == "officer_exception":
        if devices.get("officer_controlling") is not True:
            raise ValueError("officer exception source missing")
    else:
        raise ValueError("unsupported control context")
    if (routes.get("case_id") != case_id or
            not isinstance(routes.get("ego_approach"), dict) or
            not isinstance(routes.get("counterpart_route"), dict)):
        raise ValueError("original route survey missing")
    for name in ("ego_approach", "counterpart_route"):
        route = routes[name]
        if (not isinstance(route.get("road_id"), int) or
                not isinstance(route.get("lane_id"), int) or
                not isinstance(route.get("native_waypoints"), list) or
                len(route["native_waypoints"]) < 2):
            raise ValueError("source-surveyed Native route missing: " + name)
        for point in route["native_waypoints"]:
            _pose(point, name)
    if (routes["ego_approach"]["road_id"], routes["ego_approach"]["lane_id"]) == (
            routes["counterpart_route"]["road_id"], routes["counterpart_route"]["lane_id"]):
        raise ValueError("counterpart has no distinct route")
    return {"root": root, "index": index, "site": site, "devices": devices,
            "routes": routes, "source_hashes": {x["path"]: x["sha256"] for x in refs}}


class NativeAdapter:
    """Read back surveyed Native entities before spawning either participant."""

    def __init__(self, world, carla, survey, case_spec):
        self.world, self.carla, self.survey = world, carla, survey
        self.case_spec = case_spec
        if (case_spec.get("case_id") != survey["index"]["case_id"] or
                case_spec.get("control_context") != survey["devices"]["control_context"] or
                case_spec.get("cell_id") != "C158196"):
            raise ValueError("Native adapter differs from selected exact case")
        self.actors = {}
        self.target_speeds = {}
        self.map_verified = False
        self.verified = False

    def _location(self, point):
        return self.carla.Location(x=point["x"], y=point["y"], z=point["z"])

    def _route(self, name):
        route = self.survey["routes"][name]
        native_map = self.world.get_map()
        for point in route["native_waypoints"]:
            pose = _pose(point, name)
            waypoint = native_map.get_waypoint(self._location(pose), project_to_road=False)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (
                    route["road_id"], route["lane_id"]):
                raise ValueError("Native map route does not match original survey: " + name)
            p = waypoint.transform.location
            if hypot(p.x - pose["x"], p.y - pose["y"]) > 1.5:
                raise ValueError("Native waypoint drift from original survey: " + name)
        return route

    def inspect_intersection(self):
        site = self.survey["site"]
        if self.world.get_map().name != site["native_map_name"]:
            raise ValueError("Native map differs from original site")
        self._route("ego_approach")
        self._route("counterpart_route")
        bounds = site["intersection_rectangle_xy"]
        midpoint = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
        counterpart = self.survey["routes"]["counterpart_route"]["native_waypoints"][0]
        measured_station = hypot(counterpart["x"] - midpoint[0], counterpart["y"] - midpoint[1])
        planned_station = _finite(self.case_spec.get("counterpart_start_m"), "counterpart start")
        if abs(measured_station - planned_station) > 1.5:
            raise ValueError("Native counterpart start differs from frozen engineering contrast")
        self.map_verified = True
        return {"layout": site["layout"], "through_highway": site["through_highway"],
                "intersection_rectangle_xy": site["intersection_rectangle_xy"],
                "source": "site.json:" + self.survey["source_hashes"]["site.json"]}

    def inspect_devices(self):
        if not self.map_verified:
            raise ValueError("Native map readback required before device inspection")
        devices = self.survey["devices"]
        actor = self.world.get_actor(devices["ego_control_actor_id"])
        if actor is None or actor.id != devices["ego_control_actor_id"]:
            raise ValueError("surveyed controlling actor absent from Native world")
        expected = {"stop_sign": "traffic.stop", "yield_sign": "traffic.yield",
                    "signal_exception": "traffic.traffic_light", "officer_exception": "walker."}
        context = devices["control_context"]
        if not actor.type_id.startswith(expected[context]):
            raise ValueError("Native controlling actor type differs from original survey")
        if context == "signal_exception":
            state = actor.get_state()
            actual = getattr(state, "name", str(state).split(".")[-1]).lower()
            if actual != devices.get("signal_state"):
                raise ValueError("Native signal state differs from original survey")
        if context == "officer_exception" and not devices.get("original_officer_control_log"):
            raise ValueError("original officer control observation missing")
        priority = devices["counterpart_priority_source"]
        if (priority.get("route_road_id") != self.survey["routes"]["counterpart_route"]["road_id"] or
                priority.get("unobligated") is not True or
                not priority.get("original_device_survey")):
            raise ValueError("counterpart priority not established by original source")
        self.verified = True
        return {"source": "devices.json:" + self.survey["source_hashes"]["devices.json"],
                "context": context,
                "signal_controlling": devices.get("signal_controlling"),
                "exception_active": context in {"signal_exception", "officer_exception"}}

    def spawn_vehicle(self, role, spawn):
        if not self.verified:
            raise ValueError("Native map and devices must be verified before spawn")
        name = {"ego": "ego_approach", "counterpart": "counterpart_route"}.get(role)
        if name is None or spawn.get("resolve_from_native_map") is not True:
            raise ValueError("unsupported vehicle role or unresolved Native spawn")
        route = self.survey["routes"][name]
        point = _pose(route["native_waypoints"][0], name)
        location = self._location(point)
        transform = self.carla.Transform(location, self.carla.Rotation(yaw=point["yaw"]))
        blueprint_id = route.get("vehicle_blueprint")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith("vehicle."):
            raise ValueError("original vehicle blueprint missing")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None:
            raise ValueError("surveyed vehicle blueprint absent")
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("Native vehicle spawn failed")
        self.actors[role] = actor
        return actor.id

    def set_target_speed(self, actor_id, speed):
        if actor_id not in {actor.id for actor in self.actors.values()}:
            raise ValueError("target speed assigned to unowned actor")
        target = _finite(speed, "target speed")
        if not 0 < target <= 15:
            raise ValueError("target speed outside engineering range")
        # Requested speeds are controller targets, not fabricated measurements.
        # A heading-aware controller must apply controls on each Native tick.
        self.target_speeds[actor_id] = target

    def step(self, controller):
        """Apply only controls computed from original Native actor state."""
        if set(self.target_speeds) != {actor.id for actor in self.actors.values()}:
            raise ValueError("both participant targets required")
        for role, actor in self.actors.items():
            command = controller(role, actor, self.target_speeds[actor.id],
                                 self.survey["routes"]["ego_approach" if role == "ego" else "counterpart_route"],
                                 self.survey["site"]["intersection_rectangle_xy"],
                                 self.survey["devices"])
            if not isinstance(command, dict) or set(command) != {"throttle", "brake", "steer"}:
                raise ValueError("controller failed to return three Native controls")
            for key, value in command.items():
                number = _finite(value, key)
                if not ((-1 <= number <= 1) if key == "steer" else (0 <= number <= 1)):
                    raise ValueError("controller returned out-of-range control")
            actor.apply_control(self.carla.VehicleControl(**command))

    def destroy(self):
        for actor in reversed(list(self.actors.values())):
            actor.destroy()
        self.actors.clear()
        self.target_speeds.clear()
        self.map_verified = False
        self.verified = False
