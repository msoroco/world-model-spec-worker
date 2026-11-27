"""Reviewed Native construction for the moving or preparing unit approach referral."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    suffix: str
    unit_class: str = "authorized_emergency"
    light_request: str = "qualified_active"
    immediate: bool = True
    yielding: bool = True
    officer_direction: bool = False
    direction: str = "opposing"
    state: str = "moving"

CASES = (
    Case("immediate_approach_yield"),
    Case("immediate_approach_no_yield", yielding=False),
    Case("no_immediate_approach", immediate=False),
    Case("lights_inactive", light_request="qualified_inactive"),
    Case("lights_unqualified", light_request="unqualified_active"),
    Case("officer_directs_otherwise", yielding=False, officer_direction=True),
    Case("regulatory_official_yield", unit_class="regulatory_official"),
    Case("same_direction_approach_yield", direction="same_direction"),
    Case("preparing_visible_hand_signal", state="preparing"),
    Case("stopped_referral", state="stopped"),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def plan(case, map_source, actor_source, authority):
    require(case in CASES, "unselected exact case")
    require(map_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(map_source.get("road_type") == "paved_road", "paved road required")
    require(map_source.get("ego_route_connected") is True, "connected ego route required")
    require(map_source.get("unit_route_connected") is True, "connected unit route required")
    require(map_source.get("unit_route_approaches_ego") is case.immediate, "immediate approach source mismatch")
    require(map_source.get("unit_route_direction") == case.direction, "approach direction mismatch")
    require(map_source.get("unit_state") == case.state, "unit movement/preparation source mismatch")
    if case.state == "preparing":
        require(map_source.get("visible_preparation_source"), "visible preparation source required")
    if case.state == "stopped":
        require(map_source.get("stop_location_source"), "reviewed stop location source required")
    for key in ("ego_route_id", "unit_route_id", "conflict_location_source"):
        require(isinstance(map_source.get(key), str) and map_source[key], key + " missing")
    require(actor_source.get("source_kind") == "native_blueprint_readback", "Native blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id"):
        require(isinstance(actor_source.get(key), str) and actor_source[key], key + " missing")
    require(actor_source.get("ego_vehicle_class") == "ordinary_motor_vehicle",
            "every-other-vehicle subject class unverified")
    require(actor_source.get("ego_driver_control_source"),
            "subject driver control source missing")
    require(actor_source.get("unit_class") == case.unit_class, "unit class mismatch")
    require(authority.get("class") == case.unit_class, "authority class mismatch")
    for key in ("authorization_source", "light_rule_source", "equipment_source"):
        require(isinstance(authority.get(key), str) and authority[key], key + " missing")
    require(authority.get("qualifying_flashing_equipment_verified") is (case.light_request != "unqualified_active"), "flashing equipment qualification mismatch")
    if case.light_request != "qualified_inactive":
        require(authority.get("lights_can_flash") is True, "flashing capability missing")
    if case.officer_direction:
        require(authority.get("officer_direction_source"), "officer direction source required")
    return {
        "case": case.suffix,
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"], "route": "travel"},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"], "vehicle_class": case.unit_class, "route": case.direction},
        "movement": {"enabled": True, "start_s": 20.0 if case.state == "preparing" else 0.0,
                     "end_s": 20.0 if case.state == "stopped" else 36.0,
                     "target_mps": 7.0 if case.immediate else 2.0,
                     "visible_preparation": case.state == "preparing",
                     "preparation_source": map_source.get("visible_preparation_source")},
        "ego_control": {"approach_mps": 7.5, "yield_requested": case.yielding, "response_brake_start_s": 19.0, "response_brake_fraction": 0.5 if case.yielding else 0.0},
        "lights": {"qualifying": case.light_request != "unqualified_active", "active": case.light_request != "qualified_inactive", "flash_from_s": 0.0, "flash_to_s": 45.0, "equipment_source": authority["equipment_source"], "rule_source": authority["light_rule_source"]},
        "officer_direction": {"enabled": case.officer_direction, "source": authority.get("officer_direction_source")},
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
        "source": {"map": map_source, "blueprints": actor_source, "authority": authority},
    }


def execute(adapter, case, map_source, actor_source, authority, engineering=None):
    specification = plan(case, map_source, actor_source, authority)
    engineering = engineering or {}
    route_id = map_source["unit_route_id"]
    if engineering.get("alternate_unit_route"):
        route_id = map_source.get("alternate_unit_route_id")
        require(map_source.get("alternate_unit_route_connected") is True and isinstance(route_id, str) and route_id, "reviewed connected alternate unit route required")
        require(map_source.get("alternate_unit_route_direction") == case.direction, "alternate direction changed")
        require(map_source.get("alternate_unit_route_approaches_ego") is case.immediate, "alternate immediacy changed")
    start = engineering.get("response_start_s", specification["ego_control"]["response_brake_start_s"])
    require(type(start) in (int, float) and isfinite(start) and 0 <= start < 36, "response outside capture")
    specification["ego_control"]["response_brake_start_s"] = start
    ego = adapter.spawn_vehicle(specification["ego"])
    unit = adapter.spawn_vehicle(specification["unit"])
    adapter.configure_route(ego, map_source["ego_route_id"])
    adapter.configure_route(unit, route_id)
    adapter.configure_flashing_lights(unit, specification["lights"])
    adapter.configure_unit_movement(unit, specification["movement"])
    if case.state == "preparing":
        adapter.configure_visible_preparation(unit, {
            "cue": "driver_hand_signal", "from_s": 10.0, "to_s": 20.0,
            "reviewed_source": map_source["visible_preparation_source"]})
    if case.state == "stopped":
        adapter.configure_unit_stop(unit, {
            "at_s": 20.0, "reviewed_location_source": map_source["stop_location_source"]})
    if case.officer_direction:
        adapter.configure_officer_direction(specification["officer_direction"])
    adapter.configure_ego_response(ego, specification["ego_control"])
    return {"ego": ego, "unit": unit, "occluder": None, "capture_frames": specification["capture"]["frames"]}
