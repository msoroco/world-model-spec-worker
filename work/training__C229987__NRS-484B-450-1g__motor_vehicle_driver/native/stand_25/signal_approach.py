"""Saved-source measurements for NRS 484B.450(1)(g), without legal labels.

The signal's roadway station is a projection of its measured roadside position.
The caller must retain that position and the vehicle footprint in the Native
source. The calculation preserves front, centre and rear reference distances
because the statute does not resolve which vehicle reference point governs.
"""

import argparse
import json
import math
from pathlib import Path


REQUIRED_CONTEXT = (
    "highway_status_source",
    "official_signal_status_source",
    "roadside_placement_source",
    "governed_movement_source",
    "signal_indication_source",
    "halt_purpose_source",
    "other_traffic_source",
    "applicable_law_source",
    "officer_direction_source",
    "device_direction_source",
)


def _point(value, name):
    if not isinstance(value, dict) or not all(k in value for k in ("x_m", "y_m")):
        raise ValueError(f"missing raw {name} x_m/y_m")
    point = (float(value["x_m"]), float(value["y_m"]))
    if not all(math.isfinite(v) for v in point):
        raise ValueError(f"nonfinite raw {name}")
    return point


def _projection(point, origin, tangent):
    return (point[0] - origin[0]) * tangent[0] + (point[1] - origin[1]) * tangent[1]


def measure(raw):
    if raw.get("assignment_id") != "training__C229987__NRS-484B-450-1g__motor_vehicle_driver":
        raise ValueError("raw source binds another assignment")
    if raw.get("source_kind") != "native_raw_capture":
        raise ValueError("source_kind must be native_raw_capture")
    for key in REQUIRED_CONTEXT:
        if not raw.get("context_sources", {}).get(key):
            raise ValueError(f"missing context source {key}")
    geometry = raw.get("road_geometry", {})
    origin = _point(geometry.get("approach_origin"), "approach_origin")
    tangent = _point(geometry.get("approach_tangent"), "approach_tangent")
    length = math.hypot(*tangent)
    if abs(length - 1.0) > 1e-3:
        raise ValueError("approach_tangent must be unit length")
    signal = _point(raw.get("signal", {}).get("roadside_position"), "signal roadside_position")
    signal_station = _projection(signal, origin, tangent)
    uncertainty_m = float(raw.get("geometry_uncertainty_m", -1))
    if not math.isfinite(uncertainty_m) or uncertainty_m < 0:
        raise ValueError("geometry_uncertainty_m must be nonnegative and finite")
    frames = raw.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("missing raw frames")
    measured = []
    last_time = -math.inf
    for i, frame in enumerate(frames):
        time_s = float(frame["time_s"])
        speed = float(frame["speed_mps"])
        if not math.isfinite(time_s) or time_s <= last_time or not math.isfinite(speed) or speed < 0:
            raise ValueError("frame times must increase; speed must be finite and nonnegative")
        last_time = time_s
        polygon = frame.get("vehicle_footprint_xy_m")
        if not isinstance(polygon, list) or len(polygon) < 4:
            raise ValueError("missing raw four-corner vehicle footprint")
        stations = [_projection(_point(p, "footprint corner"), origin, tangent) for p in polygon]
        front = signal_station - max(stations)
        rear = signal_station - min(stations)
        centre = signal_station - (min(stations) + max(stations)) / 2
        measured.append({
            "frame_index": i,
            "time_s": time_s,
            "speed_mps": speed,
            "front_edge_to_signal_station_m": front,
            "centre_to_signal_station_m": centre,
            "rear_edge_to_signal_station_m": rear,
            "front_edge_interval_m": [front - uncertainty_m, front + uncertainty_m],
            "approach_side_geometry": "yes" if front > uncertainty_m else "no" if rear < -uncertainty_m else "uncertain",
        })
    # This is an engineering observation window, not a statutory definition of stop/stand/park.
    stationary = [f for f in measured if f["speed_mps"] <= 0.15]
    return {
        "format": "worker-signal-approach-measurement-v1",
        "assignment_id": raw.get("assignment_id"),
        "signal_roadway_station_m": signal_station,
        "roadside_signal_offset_m": abs((signal[0] - origin[0]) * tangent[1] - (signal[1] - origin[1]) * tangent[0]),
        "geometry_uncertainty_m": uncertainty_m,
        "thirty_feet_m": 9.144,
        "stationary_speed_proxy_mps": 0.15,
        "stationary_sample_count": len(stationary),
        "stationary_time_span_s": [stationary[0]["time_s"], stationary[-1]["time_s"]] if stationary else None,
        "frames": measured,
        "context_sources": raw["context_sources"],
        "legal_verdict": None,
        "limitations": [
            "Vehicle reference point and exact boundary treatment require independent statutory review.",
            "Low-speed samples do not alone establish stopping, standing, parking, cause or duration.",
            "Context source paths identify evidence to inspect; they do not establish an exception or legal conclusion.",
            "Projection to a roadway station requires later Native geometry and governed approach review.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = json.loads(Path(args.input).read_text())
    result = measure(raw)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
