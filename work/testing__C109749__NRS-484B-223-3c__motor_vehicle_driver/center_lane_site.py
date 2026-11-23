"""Portable site gate for a two-direction shared center turn lane.

The caller must populate this packet from an original Native map and a reviewed
public-highway source. A lane label alone cannot establish the statute's design.
"""

from math import hypot, isfinite


def _xy(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("missing planar waypoint")
    pair = tuple(float(v) for v in value)
    if not all(isfinite(v) for v in pair):
        raise ValueError("non-finite waypoint")
    return pair


def _direction(lane):
    points = lane.get("centreline_xy_m")
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("lane needs original centreline")
    start, end = _xy(points[0]), _xy(points[-1])
    dx, dy = end[0] - start[0], end[1] - start[1]
    magnitude = hypot(dx, dy)
    if magnitude < 10:
        raise ValueError("lane segment too short to establish direction")
    return dx / magnitude, dy / magnitude


def validate_site(packet):
    if not packet.get("native_map_source") or not packet.get("highway_review_source"):
        raise ValueError("site requires Native map and public-highway review sources")
    if packet.get("public_highway_confirmed") is not True:
        raise ValueError("public-highway status unverified")
    lanes = packet.get("lanes")
    if not isinstance(lanes, list) or len(lanes) < 3:
        raise ValueError("site requires original lane inventory")
    ids = [lane.get("id") for lane in lanes]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("lane identifiers missing or duplicated")
    centers = [lane for lane in lanes if lane.get("center_turn_lane") is True]
    if len(centers) != 1:
        raise ValueError("highway must have exactly one shared center turn lane")
    center = centers[0]
    if center.get("exclusive_turn_use") is not True or center.get("permitted_turn_directions") != ["negative", "positive"]:
        raise ValueError("bidirectional exclusive turning use unverified")
    corridor = center.get("road_id")
    if not corridor or any(lane.get("road_id") != corridor for lane in lanes if lane.get("receiving_through") or lane.get("opposing_through")):
        raise ValueError("through lanes must belong to same highway")
    receiving = [lane for lane in lanes if lane.get("receiving_through") is True]
    opposing = [lane for lane in lanes if lane.get("opposing_through") is True]
    if len(receiving) != 1 or len(opposing) != 1:
        raise ValueError("one receiving and one opposing through lane required")
    a, b = _direction(receiving[0]), _direction(opposing[0])
    if a[0] * b[0] + a[1] * b[1] > -0.8:
        raise ValueError("through directions are not opposing")
    if packet.get("entry_maneuver") != "left_turn_onto_highway":
        raise ValueError("entry is not left turn onto highway")
    if packet.get("entry_target_lane_id") != center["id"] or packet.get("merge_target_lane_id") != receiving[0]["id"]:
        raise ValueError("entry and merge targets mismatch verified lanes")
    return {"center_lane_id": center["id"], "receiving_lane_id": receiving[0]["id"],
            "opposing_lane_id": opposing[0]["id"], "road_id": corridor,
            "native_map_source": packet["native_map_source"],
            "highway_review_source": packet["highway_review_source"]}
