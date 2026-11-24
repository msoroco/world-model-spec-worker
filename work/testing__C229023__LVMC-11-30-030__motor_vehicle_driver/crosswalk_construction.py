"""CPU blueprint for a stopped lead and rear-approaching ego at a crosswalk."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID


def _point(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in raw):
        raise ValueError("finite point required")
    return [float(raw[0]), float(raw[1])]


def build(site_path: str | Path, *, crosswalk_kind: str, ego_behavior: str) -> dict:
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    if site.get("assignment_id") != ASSIGNMENT_ID or not site.get("map_id"):
        raise ValueError("source assignment and map identity required")
    if site.get("junction_kind") != "road_intersection" or site.get("alley_junction") is not False:
        raise ValueError("qualifying road intersection, not alley junction, required")
    if crosswalk_kind not in ("marked", "unmarked") or ego_behavior not in ("wait", "pass"):
        raise ValueError("supported crossing kind and ego behavior required")
    if crosswalk_kind == "unmarked":
        lines = site.get("opposite_sidewalk_lateral_lines")
        if not isinstance(lines, list) or len(lines) != 2 or not site.get("curb_or_traveled_edge_source"):
            raise ValueError("opposite sidewalk lines and curb source required")
        near, far = lines
        if any(not isinstance(line, list) or len(line) != 2 for line in lines):
            raise ValueError("two sidewalk lateral line endpoints required")
        near = [_point(p) for p in near]
        far = [_point(p) for p in far]
        if abs(near[0][0] - far[0][0]) > 0.25 or abs(near[1][0] - far[1][0]) > 0.25:
            raise ValueError("opposite sidewalk lateral lines do not connect")
        polygon = [near[0], near[1], far[1], far[0]]
    else:
        if not site.get("crosswalk_marking_source"):
            raise ValueError("marked crossing source required")
        polygon = [_point(p) for p in site.get("marked_crosswalk_polygon", [])]
        if len(polygon) < 4:
            raise ValueError("marked crossing polygon required")
    lead = _point(site.get("lead_stop_center"))
    ego = _point(site.get("ego_start_center"))
    pedestrian_start = _point(site.get("pedestrian_start"))
    pedestrian_end = _point(site.get("pedestrian_end"))
    road = site.get("road_y_bounds")
    if not isinstance(road, list) or len(road) != 2 or any(not isinstance(x, (int, float)) for x in road) or road[0] >= road[1]:
        raise ValueError("road lateral bounds required")
    if not ego[0] < lead[0] < min(p[0] for p in polygon):
        raise ValueError("ego must start behind stopped lead before crossing")
    if not (road[0] <= lead[1] <= road[1] and road[0] <= ego[1] <= road[1]):
        raise ValueError("vehicle spawn must lie in road bounds")
    if not ((pedestrian_start[1] < road[0] and pedestrian_end[1] > road[1]) or
            (pedestrian_end[1] < road[0] and pedestrian_start[1] > road[1])):
        raise ValueError("pedestrian route must cross the roadway")
    if ego_behavior == "pass":
        pass_y = site.get("pass_lane_y")
        if isinstance(pass_y, bool) or not isinstance(pass_y, (int, float)) or not road[0] <= pass_y <= road[1]:
            raise ValueError("supported road passing lane required")
        if abs(pass_y - lead[1]) < site.get("combined_vehicle_half_width_m", 2.4):
            raise ValueError("lateral passing clearance inadequate")
        ego_route = [ego, [lead[0] - 3, float(pass_y)], [max(p[0] for p in polygon) + 3, float(pass_y)]]
    else:
        ego_route = [ego, [lead[0] - 4, ego[1]]]
    return {"assignment_id": ASSIGNMENT_ID, "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "map_id": site["map_id"], "crosswalk_kind": crosswalk_kind,
            "crosswalk_polygon": polygon, "lead_stop_center": lead,
            "pedestrian_route": [pedestrian_start, pedestrian_end],
            "ego_route": ego_route, "ego_behavior": ego_behavior,
            "limit": "Geometry and route intent only; original stopped purpose, actor motion and legal crossing status require separate source review."}
