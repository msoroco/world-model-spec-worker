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
        ego_half_width = site.get("ego_half_width_m")
        combined_half_width = site.get("combined_vehicle_half_width_m")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
               for v in (ego_half_width, combined_half_width)):
            raise ValueError("positive source vehicle half widths required")
        if not road[0] + ego_half_width <= pass_y <= road[1] - ego_half_width:
            raise ValueError("passing vehicle footprint leaves road bounds")
        if abs(pass_y - lead[1]) < combined_half_width:
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


def build_sourced(site_path: str | Path, *, crosswalk_kind: str, ego_behavior: str) -> dict:
    """Bind a proposed route to regular source files beside its site packet.

    This checks source custody, not the authority or physical truth of the packet.
    """
    path = Path(site_path)
    site = json.loads(path.read_bytes())
    sources = site.get("sources")
    required = {"map", "intersection", "sidewalk", "curb_or_edge", "stopped_purpose"}
    if crosswalk_kind == "marked":
        required.add("marking")
    if not isinstance(sources, dict) or not required <= sources.keys():
        raise ValueError("complete site source inventory required")
    root = path.parent.resolve()
    inventory = {}
    used = set()
    for name in sorted(required):
        entry = sources[name]
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k] for k in ("path", "sha256", "citation")):
            raise ValueError(f"{name} source path, hash and citation required")
        if len(Path(entry["path"]).parts) != 1 or Path(entry["path"]).is_absolute():
            raise ValueError(f"{name} source path must be a portable sibling filename")
        source = path.parent / entry["path"]
        if source.is_symlink() or not source.is_file() or source.resolve().parent != root or source.resolve() == path.resolve():
            raise ValueError(f"{name} must be a distinct regular source beside the site packet")
        if source.resolve() in used:
            raise ValueError("site sources must be distinct files")
        used.add(source.resolve())
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"{name} source hash mismatch")
        inventory[name] = {"path": entry["path"], "sha256": actual, "citation": entry["citation"]}
    if site.get("map_sha256") != inventory["map"]["sha256"]:
        raise ValueError("site map hash differs from original map source")
    if site.get("curb_or_traveled_edge_source") != sources["curb_or_edge"]["citation"]:
        raise ValueError("curb source citation differs from site geometry")
    if crosswalk_kind == "marked" and site.get("crosswalk_marking_source") != sources["marking"]["citation"]:
        raise ValueError("marking source citation differs from site geometry")
    result = build(path, crosswalk_kind=crosswalk_kind, ego_behavior=ego_behavior)
    result["source_inventory"] = inventory
    result["source_status"] = "bytes_verified_authority_and_physical_truth_unreviewed"
    return result
