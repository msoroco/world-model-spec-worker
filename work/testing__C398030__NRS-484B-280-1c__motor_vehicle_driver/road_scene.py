"""Original-map school marker and pedestrian measurements; no legal cutoff."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(value):
    if not isinstance(value, list) or len(value) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("invalid original coordinate")
    return value


def load_site(path):
    """Reject a named school flag without two original boundary markers."""
    path = Path(path)
    site = json.loads(path.read_text())
    if (site.get("format"), site.get("cell_id"), site.get("layout"), site.get("control")) != (
        "worker-school-setting-site", "C398030", "school_zone", "school"
    ):
        raise ValueError("wrong school site identity")
    source = site.get("map_source", {})
    map_path = path.parent / source.get("path", "")
    if not map_path.is_file() or sha(map_path) != source.get("sha256"):
        raise ValueError("missing or stale original school map source")
    markers = site.get("school_boundary_markers")
    if not isinstance(markers, list) or len(markers) < 2:
        raise ValueError("original school boundary markers missing")
    for marker in markers:
        if not isinstance(marker, dict) or not marker.get("original_object_id") or "school" not in str(marker.get("name", "")).lower():
            raise ValueError("school marker is not an original identified object")
        pair(marker.get("location_xy_m"))
    start, end = sorted(m["location_xy_m"][0] for m in markers[:2])
    if not start < end:
        raise ValueError("school marker boundaries collapse")
    for name in ("ego_start_xy_m", "ego_end_xy_m", "pedestrian_start_xy_m", "pedestrian_end_xy_m"):
        pair(site.get(name))
    ex0, ex1 = site["ego_start_xy_m"][0], site["ego_end_xy_m"][0]
    px0, px1 = site["pedestrian_start_xy_m"][0], site["pedestrian_end_xy_m"][0]
    if not ex0 < start < px0 == px1 < end < ex1:
        raise ValueError("pedestrian not within original school marker boundaries")
    if site.get("school_designation_source") != "original Native school traffic-sign objects":
        raise ValueError("school designation provenance absent")
    if site.get("crossing_type") not in ("school_zone", "school_crossing_zone"):
        raise ValueError("school setting classification absent")
    return site


def footprint(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("missing original actor body")
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) < 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in vertex[:3]):
            raise ValueError("nonfinite original body vertex")
    return min(v[0] for v in vertices), min(v[1] for v in vertices), max(v[0] for v in vertices), max(v[1] for v in vertices)


def surface_gap(a, b):
    ax0, ay0, ax1, ay1 = footprint(a)
    bx0, by0, bx1, by1 = footprint(b)
    return math.hypot(max(bx0 - ax1, ax0 - bx1, 0), max(by0 - ay1, ay0 - by1, 0))


def observed_encounter(site, sample):
    if sample.get("pedestrian_class_source") is None or sample.get("driver_control_source") is None:
        raise ValueError("participant or driver source absent")
    if sample.get("pedestrian_class") != "pedestrian" or sample.get("ego_class") != "motor_vehicle":
        raise ValueError("wrong participant class")
    event = sample.get("driver_observation_event")
    if event is not None and (not isinstance(event, dict) or event.get("source") != "original_driver_input" or event.get("observed") is not True):
        raise ValueError("driver observation is not an original input event")
    ego, pedestrian = sample.get("ego_body_vertices_m"), sample.get("pedestrian_body_vertices_m")
    e, p = footprint(ego), footprint(pedestrian)
    markers = site["school_boundary_markers"][:2]
    start, end = sorted(m["location_xy_m"][0] for m in markers)
    if not (start <= p[0] and p[2] <= end):
        raise ValueError("pedestrian body outside original school markers")
    speed, brake = sample.get("ego_speed_mps"), sample.get("ego_brake")
    if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
        raise ValueError("original ego speed absent")
    if type(brake) not in (int, float) or not 0 <= brake <= 1:
        raise ValueError("original brake input absent")
    return {"surface_gap_m": surface_gap(ego, pedestrian),
            "longitudinal_gap_m": max(p[0] - e[2], 0),
            "pedestrian_within_original_school_markers": True,
            "school_marker_ids": [m["original_object_id"] for m in markers],
            "driver_observation_event": event, "ego_speed_mps": speed,
            "ego_brake": brake, "legal_proper_caution_verdict": None}


def controller(measurement, policy):
    """Compare engineering response timing, without a legal judgment."""
    if policy not in ("prompt_brake", "deferred_brake"):
        raise ValueError("unknown response policy")
    if not measurement.get("driver_observation_event"):
        return {"throttle": 0.25, "brake": 0.0, "steer": 0.0}
    brake = 1.0 if policy == "prompt_brake" or measurement["longitudinal_gap_m"] <= 2.0 else 0.0
    return {"throttle": 0.0 if brake else 0.25, "brake": brake, "steer": 0.0}
