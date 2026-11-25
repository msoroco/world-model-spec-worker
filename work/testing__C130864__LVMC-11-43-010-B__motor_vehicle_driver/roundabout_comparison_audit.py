"""Compare two independently captured exact roundabout cases from saved sources."""

from __future__ import annotations

from roundabout_measurements import ASSIGNMENT_ID

PAIRS = {
    "connected_entry": ("connected_wait", "connected_enter", "entry_request"),
    "adjacent_entry": ("adjacent_wait", "adjacent_enter", "entry_request"),
    "lane_relation": ("connected_enter", "adjacent_enter", "opponent_lane"),
    "gap_observation": ("connected_enter", "connected_gap_enter", "opponent_initial_gap"),
    "wider_gap_behavior": ("connected_gap_wait", "connected_gap_enter", "entry_request"),
}


def compare(comparison_id, first, second, first_packet, second_packet):
    """Enforce common physical source and declared single-variable changes."""
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact roundabout comparison")
    left_suffix, right_suffix, variable = PAIRS[comparison_id]
    if [first.get("case_id"), second.get("case_id")] != [
            ASSIGNMENT_ID + "__" + left_suffix, ASSIGNMENT_ID + "__" + right_suffix]:
        raise ValueError("comparison exact case ordering differs")
    if first.get("decoded_images") != 3600 or second.get("decoded_images") != 3600:
        raise ValueError("comparison requires two full four-camera attempts")
    left = first.get("motion", {})
    right = second.get("motion", {})
    bindings = (left.get("source_bindings", {}), right.get("source_bindings", {}))
    if not all(b.get("original_trace_sha256") for b in bindings) or (
            bindings[0]["original_trace_sha256"] == bindings[1]["original_trace_sha256"]):
        raise ValueError("comparison requires distinct original Native traces")
    fixed = ("map_sha256", "map_name", "jurisdiction_source",
             "roundabout_geometry_source", "circulating_surface_polygon",
             "entry_conflict_polygon", "circulating_lanes", "ego_entry_lane",
             "entry_line", "ego_blueprint", "opponent_blueprint", "ego_spawn",
             "ego_route")
    for key in fixed:
        if first_packet.get(key) != second_packet.get(key):
            raise ValueError("fixed comparison source changed: " + key)
    if variable == "entry_request":
        if first_packet.get("opponent_route") != second_packet.get("opponent_route") or (
                first_packet.get("opponent_spawn") != second_packet.get("opponent_spawn")) or (
                first_packet.get("opponent_points") != second_packet.get("opponent_points")) or (
                first_packet.get("opponent_release_tick") != second_packet.get("opponent_release_tick")):
            raise ValueError("fixed opponent source changed")
        if not first_packet.get("ego_release_tick", -1) > second_packet.get("ego_release_tick", 900):
            raise ValueError("entry request control did not change toward entry")
    elif variable == "opponent_lane":
        if first_packet.get("ego_release_tick") != second_packet.get("ego_release_tick") or (
                first_packet.get("opponent_release_tick") != second_packet.get("opponent_release_tick")):
            raise ValueError("fixed comparison control changed")
        if first_packet["opponent_route"]["circulating_lane_id"] == second_packet["opponent_route"]["circulating_lane_id"]:
            raise ValueError("opponent lane relation did not change")
    else:
        if first_packet.get("ego_release_tick") != second_packet.get("ego_release_tick") or (
                first_packet["opponent_route"]["circulating_lane_id"] != second_packet["opponent_route"]["circulating_lane_id"]):
            raise ValueError("fixed comparison control or lane changed")
        if first_packet.get("opponent_spawn") == second_packet.get("opponent_spawn"):
            raise ValueError("requested initial gap did not change")
    return {"comparison_id": comparison_id, "case_ids": [first["case_id"], second["case_id"]],
            "declared_variable": variable, "source_bound": True,
            "original_trace_sha256": [b["original_trace_sha256"] for b in bindings],
            "observed_entry_frames": [left.get("first_observed_ego_entry_frame"),
                                      right.get("first_observed_ego_entry_frame")],
            "observed_body_separation_at_entry_m": [left.get("body_separation_at_entry_m"),
                                                     right.get("body_separation_at_entry_m")],
            "physical_acceptance": False, "legal_verdict": None}
