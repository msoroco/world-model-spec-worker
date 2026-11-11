"""Measure a supplied pair of roadway footprints at a median opening.

This reports geometry for the frozen 30-foot separation prompt; it does not
decide statutory crossing identity or establish the truth of a source document.
"""
import math
from shapely.geometry import Polygon

THIRTY_FEET_M = 9.144


def _polygon(points, label):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("Missing " + label + " polygon")
    for point in points:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
            raise ValueError("Invalid " + label + " vertex")
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid " + label + " polygon")
    return polygon


def check_roadway_pair(document, crossing_polygon_xy_m, selected_roadway_index):
    if document.get("format") != "worker-median-roadway-geometry" or document.get("units") != "m":
        raise ValueError("Structured metre-based median geometry source required")
    if not isinstance(document.get("source_description"), str) or not document["source_description"].strip():
        raise ValueError("Median geometry source description required")
    polygons = document.get("roadway_polygons_xy_m")
    if not isinstance(polygons, list) or len(polygons) != 2:
        raise ValueError("Two roadway footprints required")
    if type(selected_roadway_index) is not int or selected_roadway_index not in (0, 1):
        raise ValueError("Selected roadway crossing index required")
    first, second = (_polygon(points, "roadway") for points in polygons)
    crossing = _polygon(crossing_polygon_xy_m, "crossing")
    gap = first.distance(second)
    selected = (first, second)[selected_roadway_index]
    if crossing.intersection(selected).area <= 0:
        raise ValueError("Selected roadway misses crossing polygon")
    at_boundary = math.isclose(gap, THIRTY_FEET_M, rel_tol=0, abs_tol=1e-9)
    separate_candidate = gap > THIRTY_FEET_M or at_boundary
    if separate_candidate and crossing.intersection((second, first)[selected_roadway_index]).area > 0:
        raise ValueError("Separate-roadway candidate polygon spans both roadway crossings")
    return {
        "roadway_edge_gap_m": gap,
        "thirty_foot_boundary_m": THIRTY_FEET_M,
        "boundary_relation": "at" if at_boundary else ("above" if gap > THIRTY_FEET_M else "below"),
        "separate_roadway_crossings_geometry_candidate": separate_candidate,
        "selected_roadway_index": selected_roadway_index,
        "statutory_crossing_identity": "unresolved",
    }
