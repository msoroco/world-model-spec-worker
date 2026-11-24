"""Original-frame observations for the two remaining NRS 484B.113(2) alternatives.

This measures complete-body intersection occupation and reverse heading through
an authored corner region. Geometry and heading changes remain observations;
actual street-corner status and legal conclusions require source review.
"""

import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon

SOURCES = ("reverse_site_context.json", "reverse_history.jsonl", "video_frames.jsonl")


def _read(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    raw = path.read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _point(values, label):
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise ValueError("Missing " + label)
    return tuple(_number(value, label) for value in values)


def _polygon(values, label):
    try:
        shape = Polygon([_point(value, label) for value in values])
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid " + label) from error
    if not shape.is_valid or shape.area <= 0:
        raise ValueError("Invalid " + label)
    return shape


def _delta_degrees(start, end):
    return (end - start + 180.0) % 360.0 - 180.0


def analyze(root, alternative):
    if alternative not in ("intersection", "street_corner"):
        raise ValueError("Unknown NRS 484B.113(2) alternative")
    root = Path(root)
    originals = {name: _read(root / name) for name in SOURCES}
    source_text = {name: item[0] for name, item in originals.items()}
    hashes = {name: item[1] for name, item in originals.items()}
    context = json.loads(source_text["reverse_site_context.json"])
    if (context.get("alternative") != alternative
            or not context.get("native_map_id")
            or not context.get("geometry_source")
            or not context.get("camera_source")):
        raise ValueError("Incomplete source-identified reverse site")
    polygon_key = ("intersection_polygon_xy_m" if alternative == "intersection"
                   else "street_corner_region_xy_m")
    region = _polygon(context.get(polygon_key), polygon_key)
    if alternative == "street_corner" and not context.get("road_topology_source"):
        raise ValueError("Missing street-corner road topology source")
    histories = [json.loads(line) for line in source_text["reverse_history.jsonl"].splitlines()
                 if line.strip()]
    frames = [json.loads(line) for line in source_text["video_frames.jsonl"].splitlines()
              if line.strip()]
    if len(histories) < 3 or len(frames) != len(histories):
        raise ValueError("Incomplete original reverse frame joins")
    samples = []
    prior = None
    for index, (row, frame) in enumerate(zip(histories, frames)):
        fid = row.get("frame")
        time = _number(row.get("time_s"), "original time")
        if (type(fid) is not int or frame.get("video_frame") != index
                or frame.get("carla_frame") != fid or frame.get("time_s") != time):
            raise ValueError("Original reverse frame join differs")
        if prior and (fid != prior["frame"] + 1 or abs(time - prior["time_s"] - .05) > 1e-3):
            raise ValueError("Original reverse sequence is not continuous 20 Hz")
        vertices = row.get("ego_body_vertices_xy_m")
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ValueError("Missing original complete vehicle body")
        body = MultiPoint([_point(vertex, "body vertex") for vertex in vertices]).convex_hull
        if body.area <= 0:
            raise ValueError("Degenerate original vehicle body")
        if type(row.get("native_reverse")) is not bool:
            raise ValueError("Missing Native reverse readback")
        heading = _number(row.get("heading_deg"), "Native heading")
        center = (body.centroid.x, body.centroid.y)
        if prior:
            forward = (math.cos(math.radians(prior["heading_deg"])),
                       math.sin(math.radians(prior["heading_deg"])))
            step = ((center[0] - prior["center"][0]) * forward[0]
                    + (center[1] - prior["center"][1]) * forward[1])
            backward = prior["native_reverse"] and row["native_reverse"] and step < 0
            turn = _delta_degrees(prior["heading_deg"], heading)
        else:
            step, backward, turn = None, False, None
        sample = {"frame": fid, "time_s": time, "native_reverse": row["native_reverse"],
                  "backward_step_m": step, "backward_motion_observed": backward,
                  "body_intersects_region": body.intersects(region),
                  "body_region_overlap_area_m2": body.intersection(region).area,
                  "heading_deg": heading, "heading_change_deg": turn,
                  "body_center_xy_m": list(center)}
        samples.append(sample)
        prior = {"frame": fid, "time_s": time, "center": center,
                 "heading_deg": heading, "native_reverse": row["native_reverse"]}
    if samples[0]["body_intersects_region"]:
        raise ValueError("Reverse start body already occupies selected region")
    reverse = [sample for sample in samples if sample["backward_motion_observed"]]
    if not reverse:
        raise ValueError("No original backward body motion")
    result = {"format": "worker-reverse-alternatives-observations",
              "alternative": alternative, "source_sha256": hashes,
              "samples": samples, "backward_motion_observed": True,
              "reverse_body_enters_region": any(
                  sample["body_intersects_region"] for sample in reverse),
              "legal_conclusion": "unresolved pending original site and camera review"}
    if alternative == "street_corner":
        result["reverse_heading_change_deg"] = _delta_degrees(
            samples[0]["heading_deg"], samples[-1]["heading_deg"])
        result["heading_change_while_in_corner_deg"] = sum(
            sample["heading_change_deg"] for sample in reverse
            if sample["body_intersects_region"])
    return result
