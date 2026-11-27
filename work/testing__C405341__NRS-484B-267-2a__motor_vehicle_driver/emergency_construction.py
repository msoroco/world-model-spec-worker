"""Source-gated Native movement-cue construction for 484B.267(2)(b)."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    suffix: str
    unit_class: str = "authorized_emergency"
    cue: str = "visible_movement"
    light_request: str = "qualified_active"
    approaching: bool = True
    officer_direction: bool = False
    reduce_speed: bool = True


CASES = (
    Case("visible_movement_preparation"),
    Case("no_movement", cue="none"),
    Case("movement_occluded", cue="occluded_movement"),
    Case("visible_hand_signal", cue="visible_hand_signal"),
    Case("already_moving", cue="already_moving"),
    Case("lights_inactive", light_request="qualified_inactive"),
    Case("lights_unqualified", light_request="unqualified_active"),
    Case("officer_directs_otherwise", officer_direction=True),
    Case("not_approaching", approaching=False),
    Case("regulatory_official", unit_class="regulatory_official"),
    Case("no_speed_reduction", reduce_speed=False),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def plan(case: Case, map_source: dict, actor_source: dict, authority: dict) -> dict:
    """Bind route, status, equipment and cue to reviewed Native readbacks."""
    require(case in CASES, "unselected case")
    require(map_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(map_source.get("road_type") == "paved_road", "paved road required")
    require(map_source.get("ego_route_connected") is True, "connected ego route required")
    require(map_source.get("unit_route_connected") is True, "connected unit route required")
    require(map_source.get("unit_route_intersects_ego_view") is True, "driver-view unit route required")
    context = map_source.get("speed_context")
    require(isinstance(context, dict) and context.get("source_kind") == "reviewed_native_conditions",
            "reviewed NRS 484B.600(1) speed context required")
    for condition in ("traffic", "surface", "highway_width", "weather", "other_highway_conditions"):
        require(isinstance(context.get(condition), dict) and
                context[condition].get("source_ref") and context[condition].get("observed_value") is not None,
                "source-bound reasonable-speed condition missing: " + condition)
    for key in ("ego_route_id", "unit_route_id"):
        require(isinstance(map_source.get(key), str) and map_source[key], key + " missing")
    require(actor_source.get("source_kind") == "native_blueprint_readback", "Native blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id"):
        require(isinstance(actor_source.get(key), str) and actor_source[key], key + " missing")
    require(actor_source.get("unit_class") == case.unit_class, "unit class mismatch")
    require(authority.get("class") == case.unit_class, "authority class mismatch")
    for key in ("authorization_source", "light_rule_source", "equipment_source"):
        require(isinstance(authority.get(key), str) and authority[key], key + " missing")
    if case.light_request.startswith("qualified"):
        require(authority.get("qualifying_flashing_equipment_verified") is True,
                "qualifying equipment source required")
    else:
        require(authority.get("qualifying_flashing_equipment_verified") is False,
                "unqualified equipment source required")
    if case.light_request.endswith("active") and case.light_request != "qualified_inactive":
        require(authority.get("lights_can_flash") is True, "light flashing capability missing")
    if case.officer_direction:
        require(authority.get("officer_direction_source"), "officer direction source required")
    if case.cue == "visible_hand_signal":
        require(actor_source.get("driver_hand_signal_capability") is True,
                "source-backed driver hand signal capability required")
    occluder = None
    if case.cue == "occluded_movement":
        occluder = map_source.get("occluder")
        require(isinstance(occluder, dict) and occluder.get("source_kind") == "native_geometry_readback",
                "constructed Native occluder required")
        require(occluder.get("blocks_driver_view") is True and occluder.get("spares_ego_route") is True,
                "occluder geometry invalid")
        require(all(type(occluder.get(k)) in (float, int) and isfinite(occluder[k]) for k in
                    ("x_m", "y_m", "length_m", "width_m", "height_m")), "occluder dimensions invalid")
        require(occluder["length_m"] > 0 and occluder["width_m"] > 0 and occluder["height_m"] > 1.4,
                "occluder cannot block driver eye")
    movement_enabled = case.cue != "none" and case.cue != "visible_hand_signal"
    movement_start = 0.0 if case.cue == "already_moving" else 17.0
    return {
        "case": case.suffix,
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"],
                "route": "approach" if case.approaching else "departing"},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"],
                 "vehicle_class": case.unit_class, "route": "cross_view"},
        "movement": {"enabled": movement_enabled, "start_s": movement_start,
                     "end_s": 19.0, "target_mps": 1.4 if movement_enabled else 0.0},
        "hand_signal": {"enabled": case.cue == "visible_hand_signal", "start_s": 16.5,
                        "end_s": 19.0},
        "ego_control": {"approach_mps": 8.0, "approaching": case.approaching,
                        "response_brake_start_s": 19.0,
                        "response_brake_fraction": 0.4 if case.reduce_speed else 0.0},
        "lights": {"qualifying": case.light_request != "unqualified_active",
                   "active": case.light_request != "qualified_inactive", "flash_from_s": 0.0,
                   "flash_to_s": 45.0, "equipment_source": authority["equipment_source"],
                   "rule_source": authority["light_rule_source"]},
        "officer_direction": {"enabled": case.officer_direction,
                              "source": authority.get("officer_direction_source")},
        "occluder": occluder,
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
        "source": {"map": map_source, "blueprints": actor_source, "authority": authority,
                   "speed_context": context},
    }


def execute(adapter, case: Case, map_source: dict, actor_source: dict,
            authority: dict, engineering: dict | None = None) -> dict:
    """Exercise Native actor operations; caller owns snapshot and restoration."""
    specification = plan(case, map_source, actor_source, authority)
    engineering = engineering or {}
    route_id = map_source["unit_route_id"]
    if engineering.get("alternate_unit_route"):
        route_id = map_source.get("alternate_unit_route_id")
        require(map_source.get("alternate_unit_route_connected") is True and
                isinstance(route_id, str) and route_id,
                "reviewed connected alternate unit route required")
    movement_start = engineering.get("movement_start_s", specification["movement"]["start_s"])
    require(type(movement_start) in (int, float) and isfinite(movement_start) and
            0 <= movement_start < specification["movement"]["end_s"],
            "reviewed movement start outside capture")
    specification["movement"]["start_s"] = movement_start
    ego = adapter.spawn_vehicle(specification["ego"])
    unit = adapter.spawn_vehicle(specification["unit"])
    adapter.configure_route(ego, map_source["ego_route_id"])
    adapter.configure_route(unit, route_id)
    adapter.configure_flashing_lights(unit, specification["lights"])
    adapter.configure_unit_movement(unit, specification["movement"])
    if specification["hand_signal"]["enabled"]:
        adapter.configure_driver_hand_signal(unit, specification["hand_signal"])
    if case.officer_direction:
        adapter.configure_officer_direction(specification["officer_direction"])
    occluder = adapter.spawn_occluder(specification["occluder"]) if specification["occluder"] else None
    adapter.configure_ego_response(ego, specification["ego_control"])
    return {"ego": ego, "unit": unit, "occluder": occluder,
            "capture_frames": specification["capture"]["frames"]}
