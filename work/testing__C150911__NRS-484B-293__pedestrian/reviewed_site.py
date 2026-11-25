"""Validate an operator-reviewed, source-hashed original C150911 site packet."""

import hashlib
import json
import math
from pathlib import Path

from crosswalk_delivery import validate_site


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_review(path, case_id):
    path = Path(path).resolve()
    document = json.loads(path.read_text())
    if document.get("case_id") != case_id or document.get("cell_id") != "C150911":
        raise ValueError("reviewed site case or cell identity differs")
    if document.get("review_status") != "original_native_reviewed":
        raise ValueError("original Native site review required")
    sources = document.get("sources")
    required = {"opendrive", "crosswalk", "pedestrian_access", "signal",
                "obstacles", "participants", "cameras"}
    if not isinstance(sources, dict) or not required <= sources.keys():
        raise ValueError("reviewed site source inventory incomplete")
    loaded = {}
    for name in sorted(required):
        ref = sources[name]
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            raise ValueError("reviewed source binding missing: " + name)
        source = (path.parent / ref["path"]).resolve()
        if not source.is_relative_to(path.parent) or not source.is_file():
            raise ValueError("reviewed source path invalid: " + name)
        if _sha(source) != ref["sha256"]:
            raise ValueError("reviewed source changed: " + name)
        loaded[name] = source.read_text() if name == "opendrive" else json.loads(source.read_text())
    crosswalk = loaded["crosswalk"]
    for key in ("crosswalk_id", "one_way_road_id", "entry_center", "exit_center",
                "crosswalk_width_m", "crosswalk_vertices_xy_m"):
        if key not in crosswalk:
            raise ValueError("reviewed crosswalk geometry missing: " + key)
    vertices = crosswalk["crosswalk_vertices_xy_m"]
    if not isinstance(vertices, list) or len(vertices) < 4 or any(
            not isinstance(v, list) or len(v) != 2 or
            not all(type(x) in (int, float) and math.isfinite(x) for x in v)
            for v in vertices):
        raise ValueError("reviewed crosswalk polygon invalid")
    cameras = loaded["cameras"]
    if set(cameras) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four reviewed camera poses required")
    for name, row in cameras.items():
        for key in ("location_xyz_m", "pitch_yaw_roll_deg"):
            value = row.get(key)
            if not isinstance(value, list) or len(value) != 3 or not all(
                    type(x) in (int, float) and math.isfinite(x) for x in value):
                raise ValueError("reviewed camera pose invalid: " + name)
    access = loaded["pedestrian_access"]
    if access.get("pedestrian_access") is not True or not access.get("method"):
        raise ValueError("reviewed pedestrian access missing")
    signal = loaded["signal"]
    if signal.get("governing_signal") not in (
            "none_read_back", "pedestrian_walk", "pedestrian_dont_walk"):
        raise ValueError("reviewed pedestrian signal missing")
    site = {key: crosswalk[key] for key in ("crosswalk_id", "one_way_road_id",
            "entry_center", "exit_center", "crosswalk_width_m")}
    site["one_way_road_id"] = str(site["one_way_road_id"])
    site.update({"map_sha256": sources["opendrive"]["sha256"],
        "crosswalk_source_sha256": sources["crosswalk"]["sha256"],
        "access_source_sha256": sources["pedestrian_access"]["sha256"],
        "signal_source_sha256": sources["signal"]["sha256"],
        "obstacle_source_sha256": sources["obstacles"]["sha256"],
        "participant_source_sha256": sources["participants"]["sha256"],
        "pedestrian_source_sha256": document.get("pedestrian_source_sha256"),
        "crosswalk_qualification": "native_crosswalk_readback",
        "governing_signal": signal["governing_signal"],
        "pedestrian_access": True})
    validate_site(site)
    return {"review_sha256": _sha(path), "sources": sources,
            "source_data": loaded, "site": site}


def verify_native_map(world, reviewed):
    """Require exact original OpenDRIVE and mapped crosswalk points before spawning."""
    mapping = world.get_map()
    if hashlib.sha256(mapping.to_opendrive().encode()).hexdigest() != reviewed["site"]["map_sha256"]:
        raise ValueError("original Native OpenDRIVE readback differs")
    observed = [(float(p.x), float(p.y)) for p in mapping.get_crosswalks()]
    if not observed:
        raise ValueError("original Native crosswalk readback absent")
    for x, y in reviewed["source_data"]["crosswalk"]["crosswalk_vertices_xy_m"]:
        if not any(math.hypot(x - ox, y - oy) <= 0.25 for ox, oy in observed):
            raise ValueError("reviewed crosswalk vertex absent from Native readback")
    road_id = int(reviewed["site"]["one_way_road_id"])
    roads = [w for pair in mapping.get_topology() for w in pair if w.road_id == road_id]
    if not roads:
        raise ValueError("reviewed one-way road absent from Native topology")
    driving = [w for w in roads if str(getattr(w, "lane_type", "Driving")).endswith("Driving")]
    signs = {1 if w.lane_id > 0 else -1 for w in driving if w.lane_id != 0}
    if len(signs) != 1:
        raise ValueError("reviewed one-way road has opposing or absent Native driving lanes")
    return True
