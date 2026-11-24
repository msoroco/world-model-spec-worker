"""Source-gated scene construction plan for a Native CARLA adapter.

An adapter implements the five methods called below. The source gates prevent
synthetic indications or scene annotations substituting for actual signal heads.
"""
from __future__ import annotations


class ConstructionError(ValueError):
    pass


CASE_PROFILES = {
    "enters_yellow": {"behavior": "traverse", "entry_phase": "yellow"},
    "enters_red": {"behavior": "traverse", "entry_phase": "red"},
    "inside_on_red": {"behavior": "traverse", "entry_phase": "yellow_before_red"},
    "red_other_route": {"behavior": "traverse", "entry_phase": "other_route_red"},
    "yellow_red": {"behavior": "traverse", "entry_phase": "yellow_to_red"},
    "stops_red": {"behavior": "stop_before_entry", "entry_phase": "none"},
    "yellow_non_alone": {"behavior": "stop_before_entry", "entry_phase": "companion_indication"},
}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def construct(adapter, scene: dict, case: str) -> dict:
    if case not in CASE_PROFILES:
        raise ConstructionError("unknown exact case")
    required = ("map_sha256", "intersection_polygon_sha256", "route_connectivity_sha256",
                "ego_blueprint", "selected_route_id", "selected_signal_id", "official_device_sha256",
                "signal_route_binding_sha256", "approach_spawn", "route_waypoints")
    if any(not scene.get(key) for key in required):
        raise ConstructionError("missing source-bound map, device, route, or ego configuration")
    if scene.get("layout") != "one_way_to_two_way_intersection":
        raise ConstructionError("wrong layout")
    if scene.get("signal_kind") != "vehicular" or scene.get("signal_facing_route_id") != scene["selected_route_id"]:
        raise ConstructionError("official facing vehicle signal not bound to ego route")
    if len(scene["route_waypoints"]) < 3 or scene.get("route_direction_sequence") != ["one_way", "intersection", "two_way"]:
        raise ConstructionError("one-way-to-two-way route connectivity unverified")
    if scene.get("duration_frames") != 900 or scene.get("rate_hz") != 20 or tuple(scene.get("cameras", ())) != CAMERAS:
        raise ConstructionError("capture profile changed")
    profile = CASE_PROFILES[case]
    if case == "yellow_non_alone" and (not scene.get("companion_signal_id") or
                                       not scene.get("companion_device_sha256") or
                                       not scene.get("companion_route_binding_sha256")):
        raise ConstructionError("companion indication source missing")
    adapter.configure_world(scene["map_sha256"], fixed_delta_seconds=0.05)
    ego = adapter.spawn_ego(scene["ego_blueprint"], scene["approach_spawn"])
    signal = adapter.bind_official_signal(scene["selected_signal_id"], scene["selected_route_id"])
    if not signal or signal.get("kind") != "vehicular" or signal.get("facing_route_id") != scene["selected_route_id"]:
        raise ConstructionError("Native official signal readback failed")
    adapter.program_signal(signal, sequence=("green", "yellow", "red"), profile=profile["entry_phase"])
    if case == "yellow_non_alone":
        companion = adapter.bind_companion_signal(scene["companion_signal_id"],
                                                  scene["selected_route_id"])
        if (not companion or companion.get("official") is not True or
            companion.get("facing_route_id") != scene["selected_route_id"] or
            companion.get("source_sha256") != scene["companion_device_sha256"]):
            raise ConstructionError("companion Native readback failed")
        adapter.program_companion_signal(companion, active_during="yellow")
    adapter.set_route_controller(ego, scene["route_waypoints"], behavior=profile["behavior"])
    for camera in CAMERAS:
        adapter.attach_camera(ego, camera)
    return {"case": case, "ego": ego, "signal": signal, "duration_frames": 900,
            "rate_hz": 20, "cameras": list(CAMERAS), "physical_outcome": "unverified"}
