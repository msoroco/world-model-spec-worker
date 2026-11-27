"""Source-gated emergency approach and curb/shoulder positioning construction.

The requests select physical variants. They do not decide whether a measured
position is legally as close as possible or whether an approach is immediate.
"""

from __future__ import annotations

from math import isfinite


SIGNED_CLASSES = frozenset({
    "authorized_emergency", "permitted_emergency", "traffic_incident_management",
    "tow_car", "coroner_vehicle", "public_transit_bus",
})
POSITIONS = frozenset({"roadway", "paved_shoulder_stop", "paved_shoulder_traverse"})


def require(value, message):
    if not value:
        raise ValueError(message)


def _source(value, name):
    require(isinstance(value, str) and value.strip(), name + " source missing")


def plan(case, map_source, actor_source, authority, shoulder_source):
    """Validate source readbacks and return a Native control specification."""
    require(map_source.get("source_kind") == "native_map_readback", "Native map readback required")
    require(map_source.get("road_type") == "paved_highway", "paved highway required")
    for key in ("highway_dedication_source", "public_access_source", "highway_boundary_source",
                "ego_route_id", "unit_route_id", "curb_or_edge_geometry_source",
                "intersection_geometry_source", "shoulder_boundary_source"):
        _source(map_source.get(key), key)
    require(map_source.get("ego_route_connected") is True, "connected subject route required")
    require(map_source.get("unit_route_connected") is True, "connected approaching unit route required")
    require(map_source.get("unit_route_approaches_ego") is case["immediate_request"],
            "immediate approach route mismatch")
    require(map_source.get("unit_route_direction") == case["approach_direction"],
            "approach direction mismatch")
    require(case["edge_type"] in ("curb", "right_edge"), "unknown right edge variant")
    require(map_source.get("selected_edge_type") == case["edge_type"], "selected edge geometry mismatch")
    if case["edge_type"] == "curb":
        require(map_source.get("curb_readback") is True, "curb physical geometry missing")
    else:
        require(map_source.get("curb_readback") is False, "no-curb segment mismatch")
    require(map_source.get("paved_shoulder_readback") is True, "paved shoulder physical geometry missing")
    require(map_source.get("roadway_shoulder_distinct") is True,
            "roadway and paved shoulder boundaries not distinguished")
    require(map_source.get("intersection_readback") is True,
            "intersection physical geometry missing")
    require(map_source.get("position_region") == case["intersection_request"],
            "intersection positioning request/source mismatch")

    require(actor_source.get("source_kind") == "native_blueprint_readback",
            "Native blueprint readback required")
    for key in ("ego_blueprint_id", "unit_blueprint_id", "ego_driver_control_source"):
        _source(actor_source.get(key), key)
    require(actor_source.get("ego_vehicle_class") == "ordinary_motor_vehicle",
            "ordinary subject vehicle source missing")
    require(actor_source.get("unit_class") == case["unit_class"], "approaching unit class mismatch")
    require(authority.get("class") == case["unit_class"], "authority class mismatch")
    for key in ("authorization_source", "light_rule_source", "equipment_source",
                "front_red_lamp_source", "siren_equipment_source", "officer_context_source"):
        _source(authority.get(key), key)
    require(authority.get("siren_equipment_verified") is True, "required siren equipment unverified")
    if case["light_request"] != "unqualified_active":
        require(authority.get("front_visible_red_lamp_verified") is True,
                "front-visible red flashing lamp source missing")
    require(authority.get("qualifying_flashing_equipment_verified") is
            (case["light_request"] != "unqualified_active"),
            "flashing equipment classification mismatch")
    if case["officer_direction_request"] != "none":
        _source(authority.get("officer_direction_source"), "law enforcement direction")

    position = case["subject_position_request"]
    require(position in POSITIONS, "unknown roadway/shoulder request")
    require(shoulder_source.get("source_kind") == "reviewed_sign_and_shoulder_readback",
            "reviewed shoulder/sign readback required")
    for key in ("shoulder_paving_source", "sign_location_source", "sign_content_source",
                "lawful_placement_source", "traffic_conflict_source"):
        _source(shoulder_source.get(key), key)
    sign_class = case["sign_permitted_class"]
    require(sign_class == "none" or sign_class in SIGNED_CLASSES,
            "unlisted shoulder-sign class")
    require(shoulder_source.get("permitted_class") == sign_class,
            "shoulder sign class/source mismatch")
    if sign_class != "none":
        require(shoulder_source.get("lawfully_placed") is True,
                "lawfully placed applicable shoulder sign not established")
        require(shoulder_source.get("sign_applies_to_segment") is True,
                "shoulder sign does not apply to position segment")
    for key in ("edge_distance_target_m", "body_yaw_target_deg"):
        number = shoulder_source.get(key)
        require(type(number) in (float, int) and isfinite(number) and number >= 0,
                "finite physical position target missing: " + key)
    require(shoulder_source.get("position_request") == position,
            "physical position/shoulder request mismatch")
    require(shoulder_source.get("parallel_request") == case["parallel_request"],
            "parallel placement request/source mismatch")
    require(shoulder_source.get("closeness_request") == case["closeness_request"],
            "curb/edge distance request/source mismatch")
    return {
        "case_id": case["case_id"],
        "ego": {"identity": "ego", "blueprint_id": actor_source["ego_blueprint_id"]},
        "unit": {"identity": "unit", "blueprint_id": actor_source["unit_blueprint_id"],
                 "vehicle_class": case["unit_class"]},
        "lights": {"active": case["light_request"] != "qualified_inactive",
                   "qualified": case["light_request"] != "unqualified_active",
                   "equipment_source": authority["equipment_source"]},
        "position": {"region": position, "edge_type": case["edge_type"],
                     "intersection": case["intersection_request"],
                     "edge_distance_target_m": shoulder_source["edge_distance_target_m"],
                     "body_yaw_target_deg": shoulder_source["body_yaw_target_deg"],
                     "sign_permitted_class": sign_class,
                     "parallel_request": case["parallel_request"],
                     "closeness_request": case["closeness_request"]},
        "movement": {"immediate_requested": case["immediate_request"],
                     "approach_direction": case["approach_direction"],
                     "officer_direction": case["officer_direction_request"]},
        "capture": {"fps": 20, "frames": 900, "cameras": 4},
    }


def execute(adapter, case, map_source, actor_source, authority, shoulder_source, engineering=None):
    """Issue concrete spawn, route, sign, shoulder and positioning calls."""
    spec = plan(case, map_source, actor_source, authority, shoulder_source)
    engineering = engineering or {}
    route_id = map_source["unit_route_id"]
    if engineering.get("alternate_unit_route"):
        route_id = map_source.get("alternate_unit_route_id")
        require(map_source.get("alternate_unit_route_connected") is True and route_id,
                "reviewed connected alternate unit route required")
        require(map_source.get("alternate_unit_route_direction") == case["approach_direction"],
                "alternate route changed approach direction")
        require(map_source.get("alternate_unit_route_approaches_ego") is case["immediate_request"],
                "alternate route changed approach condition")
    ego = adapter.spawn_vehicle(spec["ego"])
    unit = adapter.spawn_vehicle(spec["unit"])
    adapter.configure_route(ego, map_source["ego_route_id"])
    adapter.configure_route(unit, route_id)
    adapter.configure_flashing_lights(unit, spec["lights"])
    adapter.configure_unit_movement(unit, spec["movement"])
    adapter.configure_shoulder_sign(shoulder_source)
    adapter.configure_subject_position(ego, spec["position"])
    if case["officer_direction_request"] != "none":
        adapter.configure_officer_direction(authority["officer_direction_source"])
    return {"ego": ego, "unit": unit, "frames": spec["capture"]["frames"]}
