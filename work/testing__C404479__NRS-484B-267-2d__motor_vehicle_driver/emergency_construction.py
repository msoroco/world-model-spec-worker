"""Reviewed adjacent-lane source gates for NRS 484B.267(2)(d)."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    suffix: str
    maneuver: str = "hold_behind"
    unit_class: str = "authorized_emergency"
    light_request: str = "qualified_active"
    immediate: bool = True
    officer_direction: bool = False
    direction: str = "same_direction"
    state: str = "moving"

    @property
    def yielding(self):
        return self.maneuver == "hold_behind"


CASES = (
    Case("moving_hold_behind"),
    Case("moving_overtake", maneuver="overtake"),
    Case("moving_abreast", maneuver="abreast"),
    Case("unit_overtakes_ego", maneuver="unit_overtakes", immediate=False),
    Case("preparing_visible_hand_signal", state="preparing"),
    Case("lights_inactive", light_request="qualified_inactive"),
    Case("lights_unqualified", light_request="unqualified_active"),
    Case("officer_directs_otherwise", maneuver="overtake", officer_direction=True),
    Case("regulatory_official_hold_behind", unit_class="regulatory_official"),
    Case("no_approach", immediate=False),
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
    require(map_source.get("same_direction") is True, "same-direction route readback required")
    require(map_source.get("adjacent_traversable_lanes") is True, "adjacent traversable lanes required")
    require(map_source.get("ego_approaches_unit") is case.immediate, "ego approach source mismatch")
    require(map_source.get("unit_state") == case.state, "unit movement/preparation source mismatch")
    for key in ("ego_route_id", "unit_route_id", "lane_geometry_source", "passing_clearance_source"):
        require(isinstance(map_source.get(key), str) and map_source[key], key + " missing")
    if case.state == "preparing":
        require(map_source.get("visible_preparation_source"), "visible preparation source required")
    require(actor_source.get("source_kind") == "native_blueprint_readback", "Native blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id", "ego_body_extent_source", "unit_body_extent_source"):
        require(isinstance(actor_source.get(key), str) and actor_source[key], key + " missing")
    require(actor_source.get("ego_vehicle_class") == "ordinary_motor_vehicle", "ordinary other-vehicle source required")
    require(actor_source.get("ego_driver_control_source"), "subject driver source required")
    require(actor_source.get("unit_class") == case.unit_class, "unit class mismatch")
    require(authority.get("class") == case.unit_class, "authority class mismatch")
    for key in ("authorization_source", "light_rule_source", "equipment_source"):
        require(isinstance(authority.get(key), str) and authority[key], key + " missing")
    require(authority.get("qualifying_flashing_equipment_verified") is
            (case.light_request != "unqualified_active"), "equipment qualification mismatch")
    if case.light_request != "qualified_inactive":
        require(authority.get("lights_can_flash") is True, "flashing capability missing")
    if case.officer_direction:
        require(authority.get("officer_direction_source"), "officer direction source required")
    return {
        "case": case.suffix,
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"], "route": "passing_lane"},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"],
                 "vehicle_class": case.unit_class, "route": "adjacent_lane"},
        "movement": {"enabled": True, "start_s": 20.0 if case.state == "preparing" else 0.0,
                     "end_s": 36.0, "target_mps": 8.0 if case.maneuver == "unit_overtakes" else 5.0,
                     "visible_preparation": case.state == "preparing",
                     "preparation_source": map_source.get("visible_preparation_source")},
        "ego_control": {"approach_mps": 7.5, "passing_maneuver": case.maneuver,
                        "response_brake_start_s": 19.0,
                        "response_brake_fraction": 0.5 if case.maneuver == "hold_behind" else 0.0},
        "lights": {"qualifying": case.light_request != "unqualified_active",
                   "active": case.light_request != "qualified_inactive", "flash_from_s": 0.0,
                   "flash_to_s": 45.0, "equipment_source": authority["equipment_source"],
                   "rule_source": authority["light_rule_source"]},
        "officer_direction": {"enabled": case.officer_direction,
                              "source": authority.get("officer_direction_source")},
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
        "source": {"map": map_source, "blueprints": actor_source, "authority": authority},
    }


def execute(adapter, case, map_source, actor_source, authority, engineering=None):
    specification = plan(case, map_source, actor_source, authority)
    engineering = engineering or {}
    route_id = map_source["unit_route_id"]
    if engineering.get("alternate_unit_route"):
        route_id = map_source.get("alternate_unit_route_id")
        require(map_source.get("alternate_unit_route_connected") is True and route_id,
                "reviewed connected alternate unit route required")
        require(map_source.get("alternate_same_direction") is True, "alternate direction changed")
        require(map_source.get("alternate_ego_approaches_unit") is case.immediate,
                "alternate approach changed")
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
    if case.officer_direction:
        adapter.configure_officer_direction(specification["officer_direction"])
    adapter.configure_ego_response(ego, specification["ego_control"])
    return {"ego": ego, "unit": unit, "occluder": None,
            "capture_frames": specification["capture"]["frames"]}
