"""Source-gated Native lane-selection construction for NRS 484B.267(2)(e).

Requests are never interpreted as realized lane use or legal possibility. Native
readbacks and original saved frame histories decide those questions downstream.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    suffix: str
    lane_choice: str = "nonadjacent"
    condition: str = "available"
    motion_state: str = "moving"
    unit_class: str = "authorized_emergency"
    qualifying_lights: bool = True
    approaching: bool = True
    officer_direction: bool = False


CASES = (
    Case("moving_nonadjacent_lane"),
    Case("moving_adjacent_lane", lane_choice="adjacent"),
    Case("traffic_unsafe_adjacent", lane_choice="adjacent", condition="traffic_unsafe"),
    Case("roadway_impossible_adjacent", lane_choice="adjacent", condition="roadway_impossible"),
    Case("weather_unsafe_adjacent", lane_choice="adjacent", condition="weather_unsafe"),
    Case("officer_directs_adjacent", lane_choice="adjacent", officer_direction=True),
    Case("visible_movement_preparation", motion_state="preparing_movement"),
    Case("visible_hand_signal_preparation", motion_state="preparing_hand_signal"),
    Case("regulatory_official_nonadjacent", unit_class="regulatory_official"),
    Case("lights_inactive_adjacent", lane_choice="adjacent", qualifying_lights=False),
    Case("not_approaching_adjacent", lane_choice="adjacent", approaching=False),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def source_text(obj, key):
    require(isinstance(obj.get(key), str) and obj[key], key + " source missing")


def plan(case, map_source, actor_source, authority, context, engineering=None):
    require(case in CASES, "unselected exact case")
    require(map_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(map_source.get("road_type") == "paved_road", "paved road required")
    require(map_source.get("ego_route_connected") is True and map_source.get("unit_route_connected") is True,
            "connected original routes required")
    for key in ("ego_route_id", "unit_route_id", "unit_lane_id", "adjacent_lane_id", "lane_adjacency_source"):
        source_text(map_source, key)
    require(map_source.get("unit_lane_adjacent_to_ego_start") is True,
            "original unit/ego lane adjacency required")
    if case.condition != "roadway_impossible":
        source_text(map_source, "nonadjacent_lane_id")
        source_text(map_source, "nonadjacent_route_id")
        require(map_source.get("nonadjacent_route_connected") is True,
                "connected nonadjacent route required")
        require(map_source.get("nonadjacent_lane_adjacent_to_unit") is False,
                "nonadjacent lane cannot be adjacent to unit lane")
    else:
        require(map_source.get("nonadjacent_route_connected") is False,
                "roadway-impossible branch needs absent connected route")
        source_text(map_source, "nonadjacent_route_absence_source")
    require(actor_source.get("source_kind") == "native_blueprint_readback", "blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id", "ego_driver_control_source"):
        source_text(actor_source, key)
    require(actor_source.get("ego_vehicle_class") == "ordinary_motor_vehicle",
            "ordinary other-vehicle subject required")
    require(actor_source.get("unit_class") == case.unit_class and authority.get("class") == case.unit_class,
            "unit/authority class source mismatch")
    for key in ("authorization_source", "light_rule_source", "equipment_source"):
        source_text(authority, key)
    require(authority.get("qualifying_flashing_equipment_verified") is True,
            "qualifying flashing equipment source required")
    require(authority.get("lights_can_flash") is True, "flashing capability required")
    if case.officer_direction:
        source_text(authority, "officer_direction_source")
        require(authority.get("law_enforcement_officer_verified") is True,
                "law-enforcement officer authority required")
    require(context.get("source_kind") == "reviewed_native_condition_context",
            "reviewed original condition context required")
    if case.condition == "traffic_unsafe":
        require(context.get("traffic_occupies_nonadjacent_path") is True,
                "actual traffic path occupation required")
        source_text(context, "traffic_trajectory_source")
    if case.condition == "weather_unsafe":
        require(context.get("weather_adverse") is True,
                "original adverse weather source required")
        for key in ("weather_readback_source", "road_surface_source", "visibility_source"):
            source_text(context, key)
    if case.motion_state == "preparing_hand_signal":
        require(actor_source.get("driver_hand_signal_capability") is True,
                "original driver hand-signal capability required")
        source_text(actor_source, "driver_hand_signal_source")
    if case.motion_state == "preparing_movement":
        require(map_source.get("movement_cue_visible_from_ego") is True,
                "visible movement cue route/occlusion readback required")
    engineering = engineering or {}
    lane_start = engineering.get("lane_change_start_s", 17.0)
    lane_end = engineering.get("lane_change_end_s", 24.0)
    require(all(type(v) in (int, float) and isfinite(v) for v in (lane_start, lane_end)) and
            0 <= lane_start < lane_end < 40, "lane controller window outside capture")
    return {
        "case": case.suffix,
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"],
                "route": "approach" if case.approaching else "departing"},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"],
                 "vehicle_class": case.unit_class, "route": "moving_or_preparing"},
        "unit_motion": {"state": case.motion_state, "start_s": 0.0 if case.motion_state == "moving" else 18.0,
                        "target_mps": 6.0 if case.motion_state == "moving" else 1.3},
        "hand_signal": {"enabled": case.motion_state == "preparing_hand_signal",
                        "start_s": 16.0, "end_s": 23.0},
        "ego_control": {"approach_mps": 7.5, "lane_choice": case.lane_choice,
                        "lane_change_start_s": lane_start, "lane_change_end_s": lane_end,
                        "target_route_id": map_source["nonadjacent_route_id"] if case.lane_choice == "nonadjacent" else map_source["ego_route_id"]},
        "lights": {"qualifying": True, "active": case.qualifying_lights,
                   "flash_from_s": 0.0, "flash_to_s": 45.0,
                   "equipment_source": authority["equipment_source"],
                   "rule_source": authority["light_rule_source"]},
        "officer_direction": {"enabled": case.officer_direction,
                              "source": authority.get("officer_direction_source")},
        "condition": {"kind": case.condition, "source": context},
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
        "source": {"map": map_source, "blueprints": actor_source, "authority": authority},
    }


def execute(adapter, case, map_source, actor_source, authority, context, engineering=None):
    specification = plan(case, map_source, actor_source, authority, context, engineering)
    ego = adapter.spawn_vehicle(specification["ego"])
    unit = adapter.spawn_vehicle(specification["unit"])
    adapter.configure_route(ego, map_source["ego_route_id"])
    adapter.configure_route(unit, map_source["unit_route_id"])
    adapter.configure_flashing_lights(unit, specification["lights"])
    adapter.configure_unit_movement(unit, specification["unit_motion"])
    if specification["hand_signal"]["enabled"]:
        adapter.configure_hand_signal(unit, specification["hand_signal"])
    if case.condition == "traffic_unsafe":
        adapter.configure_source_bound_traffic(context)
    if case.condition == "weather_unsafe":
        adapter.configure_source_bound_weather(context)
    if case.officer_direction:
        adapter.configure_officer_direction(specification["officer_direction"])
    adapter.configure_ego_lane_route(ego, specification["ego_control"])
    return {"ego": ego, "unit": unit, "capture_frames": 900}
