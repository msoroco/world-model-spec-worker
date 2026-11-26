"""Source-bound rail-stop measurements for NRS 484B.557.

Input coordinates increase toward the nearest rail. This measures observations;
it does not decide what constitutes due care or a legal vehicle reference point.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FRAME_COUNT = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
FEET_PER_METRE = 3.280839895013123


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")
    return value


def measure(context, rows):
    if context.get("source_kind") != "native_grade_crossing_readback":
        raise ValueError("Missing Native grade-crossing readback")
    for name in ("map_sha256", "rail_geometry_sha256", "vehicle_extent_sha256",
                 "official_sign_source_sha256", "designation_source_sha256",
                 "occluder_geometry_sha256"):
        source_hash(context.get(name), name)
    if context.get("crossing_kind") != "highway_rail_at_grade":
        raise ValueError("Highway railroad grade crossing not sourced")
    if context.get("sign_governs") != "rail_crossing_approach":
        raise ValueError("Stop sign governance not sourced")
    if context.get("designation_authority") not in {"department_of_transportation", "local_with_department_approval"}:
        raise ValueError("Dangerous crossing designation authority not sourced")
    rail_x = number(context.get("nearest_track_approach_edge_x_m"), "nearest track")
    length = number(context.get("vehicle_length_m"), "vehicle length")
    if length <= 0:
        raise ValueError("Invalid vehicle length")
    if len(rows) != FRAME_COUNT:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    centers = []
    speeds = []
    visibility = []
    train = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(number(row.get("time_s"), "Native time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[c] != index for c in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        centers.append(number(row.get("vehicle_center_x_m"), "vehicle center"))
        speed = number(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        speeds.append(speed)
        sight = row.get("rail_approach_visibility")
        if sight not in {"clear", "occluded", "unknown"}:
            raise ValueError("Missing sourced rail visibility")
        visibility.append(sight)
        train_state = row.get("train_state")
        if train_state not in {"none_observed", "approaching_observed", "stationary_observed", "unknown"}:
            raise ValueError("Missing sourced train state")
        train.append(train_state)
    # These engineering detectors identify a candidate interval for independent
    # review. No duration threshold is supplied by the statute.
    stop_frames = [i for i in range(1, FRAME_COUNT - 1)
                   if speeds[i - 1] <= 0.10 and speeds[i] <= 0.10 and speeds[i + 1] <= 0.10]
    if not stop_frames:
        raise ValueError("No observed complete cessation interval")
    first_stop = stop_frames[0]
    last_stop = max(i for i in stop_frames if i >= first_stop and all(speeds[j] <= 0.10 for j in range(first_stop, i + 1)))
    if not any(centers[i] > centers[last_stop] + 1.0 and speeds[i] > 0.10 for i in range(last_stop + 1, FRAME_COUNT)):
        raise ValueError("No subsequent proceeding observed")
    if not any(centers[i] < centers[first_stop] - 1.0 and speeds[i] > 0.10 for i in range(first_stop)):
        raise ValueError("No approach before stop observed")
    # Preserve front, centre, and rear distance. The law does not name which
    # vehicle point to apply to its 15-to-50-foot band.
    center = centers[first_stop]
    distances = {
        "front_ft": (rail_x - (center + length / 2)) * FEET_PER_METRE,
        "center_ft": (rail_x - center) * FEET_PER_METRE,
        "rear_ft": (rail_x - (center - length / 2)) * FEET_PER_METRE,
    }
    return {
        "format": "worker-source-rail-stop-measurement",
        "frame_count": FRAME_COUNT,
        "rate_hz": RATE_HZ,
        "first_stop_frame": first_stop,
        "last_stop_frame": last_stop,
        "stop_reference_distances_from_nearest_track_ft": distances,
        "approach_observed": True,
        "subsequent_proceeding_observed": True,
        "visibility_at_stop": visibility[first_stop],
        "visibility_on_proceeding": sorted(set(visibility[last_stop + 1:])),
        "train_states_on_proceeding": sorted(set(train[last_stop + 1:])),
        "sign_governance_source_sha256": context["official_sign_source_sha256"],
        "designation_source_sha256": context["designation_source_sha256"],
        "legal_compliance": "unassessed",
        "due_care": "requires_independent_judgment",
        "limitations": [
            "This detector does not decide which vehicle reference point controls the statutory distance",
            "The speed threshold is an engineering detector, not a legal stop duration",
            "Visibility and train state are observed contexts, not a numeric due-care rule",
            "Designation and official sign governance require review of original source records",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    result = measure(json.loads(args.context.read_text()), rows)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
