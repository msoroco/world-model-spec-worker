"""Lazy Native construction for the six selected 484B.267(2)(c) cases.

Readback gates precede every actor call. The resulting controls are intentions;
original packets and pixels must establish movement, visibility and response.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Case:
    suffix: str
    unit_class: str = "authorized_emergency"
    cue: str = "movement"
    visible: bool = True
    brake_after_cue: bool = True
    officer_direction: bool = False


CASES = (
    Case("visible_movement_brake_response"),
    Case("visible_movement_no_brake", brake_after_cue=False),
    Case("movement_occluded", visible=False),
    Case("officer_direction", officer_direction=True),
    Case("regulatory_official_vehicle", unit_class="regulatory_official"),
    Case("hand_signal_alternative", cue="hand_signal"),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def plan(case: Case, map_source: dict, actor_source: dict, authority: dict,
         engineering: dict | None = None) -> dict:
    """Require independent map, blueprint and authority records before execution."""
    require(case in CASES, "unselected case")
    require(map_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(map_source.get("road_type") == "paved_road", "paved road required")
    require(map_source.get("ego_route_connected") is True, "connected ego approach required")
    require(map_source.get("unit_route_connected") is True, "connected unit route required")
    require(map_source.get("unit_route_intersects_ego_view") is True, "driver-view route geometry required")
    require(actor_source.get("source_kind") == "native_blueprint_readback", "Native blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id"):
        require(isinstance(actor_source.get(key), str) and actor_source[key], f"{key} missing")
    require(actor_source.get("unit_class") == case.unit_class, "unit class mismatch")
    require(authority.get("class") == case.unit_class, "authority class mismatch")
    require(isinstance(authority.get("authorization_source"), str) and authority["authorization_source"],
            "authorization source missing")
    require(isinstance(authority.get("light_rule_source"), str) and authority["light_rule_source"],
            "qualifying light rule source missing")
    require(isinstance(authority.get("equipment_source"), str) and authority["equipment_source"],
            "qualifying equipment source missing")
    require(authority.get("qualifying_flashing_equipment_verified") is True,
            "qualifying flashing equipment not verified")
    require(authority.get("lights_can_flash") is True, "flashing capability missing")
    if case.officer_direction:
        require(isinstance(authority.get("officer_direction_source"), str) and authority["officer_direction_source"],
                "officer direction source missing")
    if case.cue == "hand_signal":
        require(actor_source.get("driver_hand_signal_capability") is True,
                "driver hand-signal capability missing")
    if not case.visible:
        occlusion = map_source.get("occluder")
        require(isinstance(occlusion, dict) and occlusion.get("source_kind") == "native_geometry_readback",
                "constructed Native occluder required")
        require(occlusion.get("blocks_driver_view") is True and occlusion.get("spares_ego_route") is True,
                "occluder geometry invalid")
        require(all(type(occlusion.get(k)) in (float, int) and isfinite(occlusion[k]) for k in
                    ("x_m", "y_m", "length_m", "width_m", "height_m")), "occluder dimensions invalid")
        require(occlusion["length_m"] > 0 and occlusion["width_m"] > 0 and occlusion["height_m"] > 1.4,
                "occluder cannot block driver eye")
    engineering = engineering or {}
    movement_target = engineering.get("movement_target_mps", 1.4)
    signal_hold = engineering.get("signal_hold_to_s", 19.0)
    occluder_min = engineering.get("occluder_min_height_m", 1.4)
    require(type(movement_target) in (float, int) and 1.0 <= movement_target <= 2.5,
            "movement engineering speed invalid")
    require(type(signal_hold) in (float, int) and 19.0 <= signal_hold <= 22.0,
            "signal hold engineering invalid")
    require(type(occluder_min) in (float, int) and 1.4 <= occluder_min <= 2.2,
            "occluder height engineering invalid")
    if not case.visible:
        require(map_source["occluder"]["height_m"] >= occluder_min,
                "fallback occluder readback below target")
    return {
        "case": case.suffix,
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"], "route": "approach"},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"],
                 "vehicle_class": case.unit_class, "route": "cross_view"},
        "movement": {"start_s": 17.0, "end_s": 19.0, "target_mps": movement_target},
        "hand_signal": {"start_s": 16.5, "end_s": signal_hold, "enabled": case.cue == "hand_signal"},
        "ego_control": {"approach_mps": 8.0, "brake_after_cue": case.brake_after_cue,
                        "brake_start_s": 19.0, "brake_fraction": 0.5 if case.brake_after_cue else 0.0},
        "officer_direction": {"enabled": case.officer_direction,
                              "hold_to_s": signal_hold,
                              "source": authority.get("officer_direction_source")},
        "lights": {"qualifying": True, "flash_from_s": 0.0, "flash_to_s": 45.0,
                   "equipment_source": authority["equipment_source"],
                   "rule_source": authority["light_rule_source"]},
        "occluder": map_source.get("occluder") if not case.visible else None,
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
        "source": {"map": map_source, "blueprints": actor_source, "authority": authority},
    }


def execute(adapter, case: Case, map_source: dict, actor_source: dict, authority: dict,
            engineering: dict | None = None) -> dict:
    """Exercise actual adapter operations; caller owns snapshot and restoration."""
    specification = plan(case, map_source, actor_source, authority, engineering)
    ego = adapter.spawn_vehicle(specification["ego"])
    unit = adapter.spawn_vehicle(specification["unit"])
    adapter.configure_route(ego, map_source["ego_route_id"])
    adapter.configure_route(unit, map_source["unit_route_id"])
    adapter.configure_flashing_lights(unit, specification["lights"])
    adapter.configure_unit_movement(unit, specification["movement"])
    if case.cue == "hand_signal":
        adapter.configure_driver_hand_signal(unit, specification["hand_signal"])
    if case.officer_direction:
        adapter.configure_officer_direction(specification["officer_direction"])
    occluder = None
    if specification["occluder"] is not None:
        occluder = adapter.spawn_occluder(specification["occluder"])
    adapter.configure_ego_response(ego, specification["ego_control"])
    return {"ego": ego, "unit": unit, "occluder": occluder,
            "capture_frames": specification["capture"]["frames"]}
