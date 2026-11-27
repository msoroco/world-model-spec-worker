"""Retain a sampled incoming-lane visibility bracket without a legal finding."""

import math


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def incoming_lane_bracket(visibility, road_id, lane_id):
    """Select the actual actor's projected driving lane from original ray output."""
    unknown = {"status": "unknown", "clear_lower_bound_m": 0.0,
               "blocker_upper_bound_m": None,
               "reason": "Original incoming-lane route or horizon unavailable"}
    if not isinstance(visibility, dict):
        return unknown
    projection = visibility.get("ego_projection")
    if not isinstance(projection, dict) or projection.get("road_id") != road_id:
        return unknown
    approaches = visibility.get("approaches")
    if not isinstance(approaches, list):
        return unknown
    matches = [item for item in approaches if isinstance(item, dict) and item.get("lane_id") == lane_id]
    if len(matches) != 1:
        return unknown
    horizon = matches[0].get("any_body_sight_horizon")
    if not isinstance(horizon, dict):
        return unknown
    source = {"method": visibility.get("method"), "road_id": road_id,
              "lane_id": lane_id, "observer": "modeled incoming-lane virtual eye",
              "legal_view_obstructed": "independent_judgment_required"}
    if horizon.get("bound") == "first_sampled_occlusion":
        bracket = horizon.get("bracket_m")
        if not isinstance(bracket, list) or len(bracket) != 2 or not all(_finite(v) for v in bracket):
            return unknown
        low, high = bracket
        if low < 0 or high < low:
            return unknown
        return dict(source, status="blocked", clear_lower_bound_m=float(low),
                    blocker_upper_bound_m=float(high),
                    source_bound="first_sampled_occlusion")
    if horizon.get("bound") == "at_least":
        distance = horizon.get("distance_m")
        if not _finite(distance) or distance < 0:
            return unknown
        return dict(source, status="clear_to_limit",
                    clear_lower_bound_m=float(distance), blocker_upper_bound_m=None,
                    source_bound="at_least")
    return unknown
