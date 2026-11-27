"""Measure a source-bound center-lane traversal before a left turn from a highway.

The returned distance is an observation. Boundary and legal conclusions require
independent review of original lane geometry, body overlap and camera evidence.
"""

import math
import string

from center_lane_site import verify_reviewed_site
from center_lane_geometry import body_occupancy


FEET_PER_METER = 3.280839895013123


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(
        character in string.hexdigits for character in value)


def measure(site, frames):
    required_site = ("highway_road_id", "center_lane_id", "site_source_sha256",
                     "ego_id", "one_shared_center_lane", "turns_only_both_directions")
    if any(key not in site for key in required_site):
        raise ValueError("reviewed center-lane site context missing")
    if not _digest(site["site_source_sha256"]) or not site["highway_road_id"] or not site["center_lane_id"]:
        raise ValueError("source-bound highway or lane identity missing")
    if not site["one_shared_center_lane"] or not site["turns_only_both_directions"]:
        raise ValueError("single bidirectional turn-only center lane not established")
    required_frame = ("original_frame", "time_s", "driver_id", "road_id", "lane_id",
                      "x_m", "y_m", "body_overlaps_center_lane", "body_within_center_lane",
                      "maneuver", "source_sha256")
    if len(frames) < 3 or any(any(key not in row for key in required_frame) for row in frames):
        raise ValueError("complete original-frame route required")
    if any(row["driver_id"] != site["ego_id"] or not _digest(row["source_sha256"]) for row in frames):
        raise ValueError("driver or original route source changed")
    first_frame = frames[0]["original_frame"]
    first_time = frames[0]["time_s"]
    if type(first_frame) is not int or not math.isfinite(first_time):
        raise ValueError("invalid original frame origin")
    for index, row in enumerate(frames):
        if type(row["original_frame"]) is not int or row["original_frame"] != first_frame + index:
            raise ValueError("original frame identity discontinuity")
        if not math.isfinite(row["time_s"]) or abs(row["time_s"] - first_time - index / 20) > 0.005:
            raise ValueError("original 20 Hz time join failed")
        if not all(math.isfinite(row[key]) for key in ("x_m", "y_m")):
            raise ValueError("original position missing")
        if type(row["body_overlaps_center_lane"]) is not bool or type(row["body_within_center_lane"]) is not bool:
            raise ValueError("original body geometry readback missing")
        if row["body_within_center_lane"] and not row["body_overlaps_center_lane"]:
            raise ValueError("body containment contradicts lane overlap")
        if row["body_overlaps_center_lane"] and row["lane_id"] != site["center_lane_id"]:
            raise ValueError("center-lane body and lane identity disagree")
    if frames[0]["road_id"] != site["highway_road_id"]:
        raise ValueError("route does not approach from highway")
    occupied = [i for i, row in enumerate(frames) if row["body_overlaps_center_lane"]]
    if not occupied:
        raise ValueError("center-lane body occupancy absent")
    start, end = occupied[0], occupied[-1]
    if occupied != list(range(start, end + 1)):
        raise ValueError("interrupted center-lane occupancy requires separate review")
    if not any(frames[i]["body_within_center_lane"] for i in occupied):
        raise ValueError("full-body center-lane occupancy absent")
    departures = [i for i, row in enumerate(frames)
                  if row["maneuver"] == "left_turn" and row["road_id"] != site["highway_road_id"]]
    if len(departures) != 1 or departures[0] <= end:
        raise ValueError("connected left-turn departure from highway missing")
    if any(row["road_id"] != site["highway_road_id"] for row in frames[start:end + 1]):
        raise ValueError("center-lane travel left highway before turn")
    meters = sum(math.hypot(frames[i + 1]["x_m"] - frames[i]["x_m"],
                            frames[i + 1]["y_m"] - frames[i]["y_m"])
                 for i in range(start, end))
    feet = meters * FEET_PER_METER
    return {
        "entry_original_frame": frames[start]["original_frame"],
        "last_occupancy_original_frame": frames[end]["original_frame"],
        "left_turn_departure_original_frame": frames[departures[0]]["original_frame"],
        "observed_center_lane_path_m": meters,
        "observed_center_lane_path_ft": feet,
        "statutory_boundary_ft": 200,
        "boundary_relation_observed": "below" if feet < 200 else ("above" if feet > 200 else "at"),
        "entry_exit_interpolation": "unresolved",
        "legal_judgment": None,
        "site_source_sha256": site["site_source_sha256"],
        "route_source_sha256": list(dict.fromkeys(row["source_sha256"] for row in frames)),
    }


def measure_with_original_body(site, frames):
    """Derive occupancy from eight original body vertices and reviewed lane geometry."""
    polygon = site.get("center_lane_polygon_xy_m")
    if not polygon:
        raise ValueError("reviewed center-lane body polygon missing")
    sourced = derive_body_occupancy(site, frames)
    result = measure(site, sourced)
    result["body_occupancy_source"] = "original eight-vertex footprint against reviewed lane polygon"
    return result


def derive_body_occupancy(site, frames):
    """Replace optional readback flags with independently computed geometry."""
    polygon = site.get("center_lane_polygon_xy_m")
    if not polygon:
        raise ValueError("reviewed center-lane body polygon missing")
    sourced = []
    for row in frames:
        if "body_vertices_m" not in row:
            raise ValueError("original body vertices missing")
        geometry = body_occupancy(polygon, row["body_vertices_m"])
        for key, value in geometry.items():
            if key in row and row[key] != value:
                raise ValueError("original body geometry readback differs from reviewed lane polygon")
        sourced.append(dict(row, **geometry))
    return sourced


def measure_exact(attempt_root, packet, case_kind, live_opendrive, frames):
    """Join the reviewed map/site bytes to an exact route measurement."""
    topology = verify_reviewed_site(attempt_root, packet, case_kind, live_opendrive)
    ego_id = packet.get("ego_id")
    if not ego_id:
        raise ValueError("reviewed ego identity missing")
    review = packet.get("highway_review_source", {})
    site = {
        "highway_road_id": topology["highway_road_id"],
        "center_lane_id": topology["center_lane_id"],
        "site_source_sha256": review.get("sha256"),
        "ego_id": ego_id,
        "one_shared_center_lane": True,
        "turns_only_both_directions": True,
        "center_lane_polygon_xy_m": topology["center_lane_polygon_xy_m"],
    }
    if case_kind != "onto_highway_contrast":
        result = measure_with_original_body(site, frames)
        result["exact_case_kind"] = case_kind
        result["distance_restriction_applicable"] = True
        return result
    if len(frames) < 3 or not _digest(site["site_source_sha256"]):
        raise ValueError("original contrast route or site source missing")
    if frames[0].get("road_id") == topology["highway_road_id"] or frames[-1].get("road_id") != topology["highway_road_id"]:
        raise ValueError("contrast route is not a turn onto highway")
    if not any(row.get("maneuver") == "left_turn" for row in frames):
        raise ValueError("original contrast left turn missing")
    first_frame = frames[0].get("original_frame")
    first_time = frames[0].get("time_s")
    if type(first_frame) is not int or not isinstance(first_time, (float, int)) or not math.isfinite(first_time):
        raise ValueError("original contrast frame or time origin missing")
    for index, row in enumerate(frames):
        if (type(row.get("original_frame")) is not int or
                row["original_frame"] != first_frame + index or
                not isinstance(row.get("time_s"), (float, int)) or
                not math.isfinite(row["time_s"]) or
                abs(row["time_s"] - first_time - index / 20) > .005 or
                row.get("driver_id") != ego_id or
                not _digest(row.get("source_sha256"))):
            raise ValueError("original contrast frame, time, driver or source join failed")
    sourced = derive_body_occupancy(site, frames)
    occupied = [row for row in sourced if row.get("body_overlaps_center_lane") is True and
                row.get("lane_id") == topology["center_lane_id"]]
    if not occupied or not any(row.get("body_within_center_lane") is True for row in occupied):
        raise ValueError("original contrast center-lane body occupancy missing")
    occupied_indices = [i for i, row in enumerate(sourced) if row["body_overlaps_center_lane"]]
    if occupied_indices != list(range(occupied_indices[0], occupied_indices[-1] + 1)):
        raise ValueError("interrupted contrast center-lane occupancy requires separate review")
    return {
        "exact_case_kind": case_kind,
        "distance_restriction_applicable": False,
        "observed_turn_onto_highway": True,
        "legal_judgment": None,
        "site_source_sha256": site["site_source_sha256"],
        "body_occupancy_source": "original eight-vertex footprint against reviewed lane polygon",
        "route_source_sha256": list(dict.fromkeys(row["source_sha256"] for row in frames)),
    }
