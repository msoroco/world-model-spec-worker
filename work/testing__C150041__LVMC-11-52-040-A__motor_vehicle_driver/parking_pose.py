"""Construct requested parking poses from inspected roadway geometry."""
from __future__ import annotations

import math

from parking_measurement import inside, unit, vector


REQUESTS = {
    "park_parallel_lawful": ("park", "parallel", "lawful"),
    "park_angled_lawful": ("park", "angled", "lawful"),
    "park_parallel_reverse": ("park", "parallel", "reverse"),
    "stand_parallel_lawful": ("stand", "parallel", "lawful"),
    "stand_angled_lawful": ("stand", "angled", "lawful"),
    "stand_parallel_reverse": ("stand", "parallel", "reverse"),
}


def body(center, forward, *, length_m, width_m):
    if length_m <= 0 or width_m <= 0:
        raise ValueError("vehicle dimensions must be positive")
    lateral = (-forward[1], forward[0])
    return [[center[i] + along * length_m / 2 * forward[i] +
             across * width_m / 2 * lateral[i] for i in (0, 1)]
            for along, across in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def construct(context, suffix, *, segment_index=0, edge_offset_m=2.5,
              length_m=4.5, width_m=2.0, angle_deg=30):
    if suffix not in REQUESTS:
        raise ValueError("unknown exact standing/parking pose")
    if not isinstance(segment_index, int) or segment_index < 0:
        raise ValueError("road edge segment index invalid")
    edge = context["road_edge_xy_m"]
    if segment_index + 1 >= len(edge):
        raise ValueError("road edge segment missing")
    start, end = edge[segment_index:segment_index + 2]
    tangent = unit(vector(start, end))
    lawful = unit(context["lawful_travel_xy"])
    if abs(sum(tangent[i] * lawful[i] for i in (0, 1))) < .9:
        raise ValueError("lawful travel direction conflicts with selected edge")
    if not math.isfinite(edge_offset_m) or edge_offset_m <= 0:
        raise ValueError("edge offset must be positive")
    anchor = tuple((start[i] + end[i]) / 2 for i in (0, 1))
    normals = ((-tangent[1], tangent[0]), (tangent[1], -tangent[0]))
    candidates = [tuple(anchor[i] + edge_offset_m * normal[i] for i in (0, 1))
                  for normal in normals]
    choices = [(normal, center) for normal, center in zip(normals, candidates)
               if inside(center, context["roadway_polygon_xy_m"])]
    if len(choices) != 1:
        raise ValueError("inspected roadway does not identify one inward edge side")
    inward, center = choices[0]
    activity, orientation, heading = REQUESTS[suffix]
    direction = lawful if heading == "lawful" else tuple(-value for value in lawful)
    if orientation == "angled":
        if not 0 < angle_deg < 90:
            raise ValueError("engineering angled pose must be between parallel and perpendicular")
        radians = math.radians(angle_deg)
        direction = unit(tuple(math.cos(radians) * lawful[i] +
                               math.sin(radians) * inward[i] for i in (0, 1)))
    corners = body(center, direction, length_m=length_m, width_m=width_m)
    if not all(inside(point, context["roadway_polygon_xy_m"]) for point in corners):
        raise ValueError("requested full vehicle footprint leaves inspected roadway")
    return {"activity_request": activity, "orientation_request": orientation,
            "heading_request": heading, "target_center_xy_m": center,
            "target_forward_xy": direction, "target_body_vertices_xy_m": corners,
            "road_edge_segment_index": segment_index, "edge_offset_request_m": edge_offset_m,
            "engineering_angle_request_deg": angle_deg if orientation == "angled" else 0,
            "source_packet_sha256": context["reviewed_packet_sha256"],
            "lawful_direction_source": context["lawful_direction_source"],
            "physical_realization_claimed": False, "legal_judgment": "unresolved"}
