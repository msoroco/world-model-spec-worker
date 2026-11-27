"""Source-bound crosswalk context for NRS 484B.280(1)(c).

The measured crossing kind is an original scene fact. Neither crossing kind nor
response timing assigns a legal meaning to proper caution.
"""

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("original finite XY point required")
    return tuple(float(x) for x in value)


def polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("original polygon missing")
    return [point(x) for x in value]


def _inside(p, vertices):
    inside = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if ((a[1] > p[1]) != (b[1] > p[1]) and
                p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])):
            inside = not inside
    return inside


def load_site(path, expected_case):
    """Require hashed map, intersecting roads, both curbs and a crossing route."""
    path = Path(path)
    site = json.loads(path.read_text())
    case_prefix = "testing__C230221__NRS-484B-280-1c__motor_vehicle_driver__"
    kind = expected_case.removeprefix(case_prefix).removesuffix("_crosswalk")
    if (expected_case != case_prefix + kind + "_crosswalk" or
            kind not in ("marked", "unmarked") or
            site.get("case_id") != expected_case or
            site.get("cell_id") != "C230221" or
            site.get("layout") != "road" or
            site.get("control") != "crosswalk" or
            site.get("crosswalk_kind") != kind):
        raise ValueError("crosswalk source identity mismatch")
    source = site.get("map_source", {})
    map_path = (path.parent / source.get("path", "")).resolve()
    if not map_path.is_file() or sha(map_path) != source.get("sha256"):
        raise ValueError("original OpenDRIVE source absent or changed")
    root = ElementTree.fromstring(map_path.read_bytes())
    roads = {r.get("id") for r in root.findall(".//road")}
    ids = site.get("intersecting_road_ids")
    if not isinstance(ids, list) or len(ids) < 2 or not set(ids) <= roads:
        raise ValueError("intersecting source roads absent")
    if not site.get("intersection_review_source") or not site.get("curb_review_source"):
        raise ValueError("intersection or curb source review absent")
    crossing = polygon(site.get("crossing_polygon_xy_m"))
    curbs = [polygon(site.get(name)) for name in ("near_curb_polygon_xy_m", "far_curb_polygon_xy_m")]
    route = [point(x) for x in site.get("pedestrian_route_xy_m", [])]
    ego_route = [point(x) for x in site.get("ego_route_xy_m", [])]
    if (len(route) < 3 or len(ego_route) < 2 or
            not _inside(route[0], curbs[0]) or not _inside(route[-1], curbs[1]) or
            not any(_inside(p, crossing) for p in route[1:-1])):
        raise ValueError("source crossing route or curb continuity absent")
    objects = {o.get("id"): o for o in root.findall(".//object")}
    marking_id = site.get("marking_object_id")
    if kind == "marked":
        if not marking_id or marking_id not in objects or objects[marking_id].get("type") != "crosswalk":
            raise ValueError("original crosswalk marking absent")
    elif marking_id is not None or any(o.get("type") == "crosswalk" for o in objects.values()):
        raise ValueError("unmarked crossing contains a marking")
    return site


def author_from_native(map_bytes, readback, output, expected_case):
    """Seal original map and surveyed geometry before any crossing measurement.

    The caller must acquire ``map_bytes`` and ``readback`` from the active Native
    world. This routine rejects an authored label without a source identity.
    """
    if not isinstance(map_bytes, bytes) or not map_bytes:
        raise ValueError("original Native map bytes required")
    if (not isinstance(readback, dict) or readback.get("source") != "original_native_readback" or
            readback.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest() or
            readback.get("case_id") != expected_case):
        raise ValueError("original Native source binding missing")
    output = Path(output)
    if not output.is_dir():
        raise ValueError("Native output directory missing")
    map_path, site_path = output / "map.xodr", output / "crosswalk-site.json"
    if map_path.exists() or site_path.exists():
        raise ValueError("original source output must be fresh")
    map_path.write_bytes(map_bytes)
    fields = ("case_id", "cell_id", "layout", "control", "crosswalk_kind",
              "intersecting_road_ids", "intersection_review_source", "curb_review_source",
              "crossing_polygon_xy_m", "near_curb_polygon_xy_m", "far_curb_polygon_xy_m",
              "pedestrian_route_xy_m", "ego_route_xy_m", "marking_object_id")
    site = {name: readback.get(name) for name in fields}
    site["map_source"] = {"path": map_path.name, "sha256": sha(map_path)}
    site_path.write_text(json.dumps(site, indent=2, allow_nan=False) + "\n")
    return load_site(site_path, expected_case)


def footprint(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("original body vertices absent")
    points = [point(v[:2]) for v in vertices if isinstance(v, list) and len(v) >= 3]
    if len(points) != len(vertices):
        raise ValueError("original body vertex invalid")
    return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)


def measure(site, sample):
    """Keep original driver input separate from camera visibility."""
    if (sample.get("ego_class") != "motor_vehicle" or
            sample.get("pedestrian_class") != "pedestrian" or
            not sample.get("driver_control_source") or
            not sample.get("pedestrian_class_source")):
        raise ValueError("original participant classification absent")
    ego = footprint(sample.get("ego_body_vertices_m"))
    ped = footprint(sample.get("pedestrian_body_vertices_m"))
    center = ((ped[0] + ped[2]) / 2, (ped[1] + ped[3]) / 2)
    if not _inside(center, polygon(site["crossing_polygon_xy_m"])):
        raise ValueError("pedestrian body outside reviewed crossing")
    event = sample.get("driver_observation_event")
    if event is not None and (not isinstance(event, dict) or
                              event.get("source") != "original_driver_input" or
                              event.get("observed") is not True):
        raise ValueError("driver observation lacks original input")
    speed, brake = sample.get("ego_speed_mps"), sample.get("ego_brake")
    if (type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0 or
            type(brake) not in (int, float) or not 0 <= brake <= 1):
        raise ValueError("original control history absent")
    return {"crosswalk_kind": site["crosswalk_kind"],
            "longitudinal_gap_m": max(ped[0] - ego[2], 0),
            "driver_observation_event": event, "ego_speed_mps": speed,
            "ego_brake": brake, "legal_proper_caution_verdict": None}
