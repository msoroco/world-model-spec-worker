"""Source-bound geometric observations for LVMC 11.52.040(A) CPU preparation.

Input is a saved Native trace extract plus independently identified roadway
geometry. The tool measures geometry; it does not decide legal compliance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unit(vector):
    if len(vector) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
        raise ValueError("invalid finite 2D vector")
    size = math.hypot(*vector)
    if size <= 0:
        raise ValueError("zero-length direction vector")
    return [vector[0] / size, vector[1] / size]


def angle_degrees(a, b, *, unsigned=False):
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
    if unsigned:
        dot = abs(dot)
    return math.degrees(math.acos(dot))


def measure(trace, geometry):
    if trace.get("format") != "worker-saved-pose-extract":
        raise ValueError("missing saved pose extract format")
    if geometry.get("format") != "worker-road-edge-context":
        raise ValueError("missing road edge context format")
    if not trace.get("native_trace_path") or not trace.get("native_trace_sha256"):
        raise ValueError("missing Native trace provenance")
    if not geometry.get("source_path") or not geometry.get("source_sha256"):
        raise ValueError("missing geometry provenance")
    if geometry.get("roadway_class") != "roadway" or not geometry.get("road_edge_identified"):
        raise ValueError("roadway and edge must be identified")
    edge = unit(geometry["edge_tangent_xy"])
    lawful = unit(geometry["lawful_traffic_direction_xy"])
    frames = trace.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("need at least two saved pose frames")
    observations = []
    previous = None
    for frame in frames:
        if not all(key in frame for key in ("frame", "time_s", "heading_deg", "speed_mps", "center_xy")):
            raise ValueError("incomplete saved pose frame")
        t = frame["time_s"]
        speed = frame["speed_mps"]
        xy = frame["center_xy"]
        heading = frame["heading_deg"]
        if (not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (t, speed, heading))
                or speed < 0 or len(xy) != 2
                or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in xy)):
            raise ValueError("invalid saved pose sample")
        if previous is not None and (frame["frame"] <= previous[0] or t <= previous[1]):
            raise ValueError("saved pose frames are not strictly ordered")
        previous = (frame["frame"], t)
        vector = [math.cos(math.radians(heading)), math.sin(math.radians(heading))]
        observations.append({
            "frame": frame["frame"],
            "time_s": t,
            "speed_mps": speed,
            "center_xy": xy,
            "heading_deg": heading,
            "edge_parallel_angle_deg": angle_degrees(vector, edge, unsigned=True),
            "lawful_traffic_heading_angle_deg": angle_degrees(vector, lawful),
        })
    return {
        "format": "worker-roadside-pose-observations",
        "native_trace_path": trace["native_trace_path"],
        "native_trace_sha256": trace["native_trace_sha256"],
        "geometry_source_path": geometry["source_path"],
        "geometry_source_sha256": geometry["source_sha256"],
        "observations": observations,
        "interpretation": "Angles and speed are measurements only; standing/parking purpose, Chapter exceptions and legal judgment require independent evidence.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    trace_path, geometry_path = Path(args.trace), Path(args.geometry)
    trace, geometry = json.loads(trace_path.read_text()), json.loads(geometry_path.read_text())
    if trace.get("native_trace_sha256") != digest(trace["native_trace_path"]):
        raise ValueError("Native trace hash mismatch")
    if geometry.get("source_sha256") != digest(geometry["source_path"]):
        raise ValueError("geometry source hash mismatch")
    result = measure(trace, geometry)
    result["saved_pose_extract_sha256"] = digest(trace_path)
    result["road_edge_context_sha256"] = digest(geometry_path)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
