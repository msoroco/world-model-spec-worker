"""Source-gated road and pedestrian geometry for the assigned cell.

All distances here are construction coordinates or measurements. None defines
"near" or "proper caution" in NRS 484B.280(1)(c).
"""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_pair(value):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise ValueError("invalid source coordinate")
    return value


def load_site(path):
    """Require reviewed road edges and actual map source before placement."""
    path = Path(path)
    site = json.loads(path.read_text())
    if site.get("format") != "worker-on-road-site" or site.get("cell_id") != "C233871":
        raise ValueError("wrong road site identity")
    if site.get("layout") != "road_without_sidewalk" or site.get("sidewalk_present") is not False:
        raise ValueError("absence of sidewalk not reviewed")
    source = site.get("map_source", {})
    map_path = path.parent / source.get("path", "")
    if not map_path.is_file() or sha(map_path) != source.get("sha256"):
        raise ValueError("missing or stale original road map source")
    road = site.get("road", {})
    lo, hi = road.get("lateral_bounds_m", [None, None])
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (lo, hi)) or lo >= hi:
        raise ValueError("unreviewed original road bounds")
    if not road.get("classification_source") or not road.get("edge_review_source"):
        raise ValueError("road classification or edges unreviewed")
    for key in ("ego_start_xy_m", "ego_end_xy_m", "pedestrian_start_xy_m", "pedestrian_end_xy_m"):
        finite_pair(site.get(key))
    p0, p1 = site["pedestrian_start_xy_m"], site["pedestrian_end_xy_m"]
    if not (lo <= p0[1] <= hi and lo <= p1[1] <= hi):
        raise ValueError("pedestrian route is not on the road")
    if not (site["ego_start_xy_m"][0] < p0[0] < site["ego_end_xy_m"][0]):
        raise ValueError("ego route does not approach the pedestrian")
    return site


def footprint(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("missing original actor body")
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) < 3 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in vertex[:3]
        ):
            raise ValueError("nonfinite original body vertex")
    return min(v[0] for v in vertices), min(v[1] for v in vertices), max(v[0] for v in vertices), max(v[1] for v in vertices)


def surface_gap(ego, pedestrian):
    ex0, ey0, ex1, ey1 = footprint(ego)
    px0, py0, px1, py1 = footprint(pedestrian)
    return math.hypot(max(px0 - ex1, ex0 - px1, 0), max(py0 - ey1, ey0 - py1, 0))


def observed_encounter(site, sample):
    """Measure original bodies and a separate driver observation event source."""
    if sample.get("pedestrian_class_source") is None or sample.get("driver_control_source") is None:
        raise ValueError("participant classification or driver source absent")
    if sample.get("pedestrian_class") != "pedestrian" or sample.get("ego_class") != "motor_vehicle":
        raise ValueError("wrong participant classification")
    event = sample.get("driver_observation_event")
    if event is not None and (event.get("source") != "original_driver_input" or event.get("observed") is not True):
        raise ValueError("driver observation is not an original input event")
    ego = sample.get("ego_body_vertices_m")
    pedestrian = sample.get("pedestrian_body_vertices_m")
    e = footprint(ego)
    p = footprint(pedestrian)
    lo, hi = site["road"]["lateral_bounds_m"]
    if p[1] < lo or p[3] > hi:
        raise ValueError("pedestrian body outside reviewed road")
    speed = sample.get("ego_speed_mps")
    brake = sample.get("ego_brake")
    if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
        raise ValueError("original ego speed absent")
    if type(brake) not in (int, float) or not 0 <= brake <= 1:
        raise ValueError("original brake command absent")
    return {"surface_gap_m": surface_gap(ego, pedestrian),
            "longitudinal_gap_m": max(p[0] - e[2], 0),
            "pedestrian_on_reviewed_road": True,
            "driver_observation_event": event,
            "ego_speed_mps": speed, "ego_brake": brake,
            "legal_proper_caution_verdict": None}


def controller(measurement, policy):
    """An engineering response to an actual driver-input event, not a legal test."""
    if policy not in ("prompt_brake", "deferred_brake"):
        raise ValueError("unknown response policy")
    if not measurement.get("driver_observation_event"):
        return {"throttle": 0.25, "brake": 0.0, "steer": 0.0}
    if policy == "prompt_brake":
        brake = 1.0
    else:
        brake = 1.0 if measurement["longitudinal_gap_m"] <= 2.0 else 0.0
    return {"throttle": 0.0 if brake else 0.25, "brake": brake, "steer": 0.0}
