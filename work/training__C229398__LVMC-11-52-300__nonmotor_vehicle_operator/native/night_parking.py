"""Source-bound diagnostic meter for LVMC 11.52.300 parking duration.

This measures an observed episode. It never decides whether a device is a
vehicle under the ordinance or whether a person legally parked it.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


FRAME_RATE = 20
WINDOW_START_HOUR = 1
WINDOW_END_HOUR = 6
LIMIT_MS = 30 * 60 * 1000
SOURCE_NAMES = ("classification", "street", "parking", "civil_clock", "frame_map")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(observations_path, provenance_path):
    provenance = json.loads(Path(provenance_path).read_text())
    if provenance.get("format") != "worker-night-parking-provenance" or provenance.get("mode") not in ("diagnostic", "native"):
        raise ValueError("Invalid source provenance")
    sources = provenance.get("sources", {})
    for name in SOURCE_NAMES:
        item = sources.get(name)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("Missing source: " + name)
        path = Path(item["path"])
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise ValueError("Source hash mismatch: " + name)
    if Path(sources["frame_map"]["path"]).resolve() != Path(observations_path).resolve():
        raise ValueError("Frame map source is not observations")
    classification = json.loads(Path(sources["classification"]["path"]).read_text())
    street = json.loads(Path(sources["street"]["path"]).read_text())
    parking = json.loads(Path(sources["parking"]["path"]).read_text())
    civil_clock = json.loads(Path(sources["civil_clock"]["path"]).read_text())
    device_class = classification.get("device_class")
    if device_class not in ("motor_vehicle", "qualifying_nonmotor_vehicle", "unresolved"):
        raise ValueError("Device class unresolved")
    if parking.get("activity_annotation") != "parked":
        raise ValueError("Parking activity source unresolved")
    bounds = street.get("street_bounds_xy_m")
    if not isinstance(bounds, list) or len(bounds) != 4 or not all(type(v) in (int, float) for v in bounds):
        raise ValueError("Street geometry source unresolved")
    if civil_clock.get("timezone") != provenance.get("timezone"):
        raise ValueError("Civil clock source differs")
    zone = ZoneInfo(provenance["timezone"])
    first_ms = last_ms = previous_ms = None
    longest_ms = 0
    current_start = None
    previous_frame = -1
    count = 0
    with Path(observations_path).open() as stream:
        for line in stream:
            row = json.loads(line)
            frame = row.get("frame")
            ms = row.get("utc_epoch_ms")
            if frame != previous_frame + 1 or not isinstance(ms, int):
                raise ValueError("Incomplete or nonmonotonic frame map")
            if previous_ms is not None and ms - previous_ms != 50:
                raise ValueError("Civil time join differs from 20 Hz frame map")
            velocity = row.get("actor_velocity_mps")
            center = row.get("actor_center_xy_m")
            if type(velocity) not in (int, float) or not isinstance(center, list) or len(center) != 2 or not all(type(v) in (int, float) for v in center):
                raise ValueError("Missing raw actor velocity or position")
            local = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(zone)
            inside = WINDOW_START_HOUR <= local.hour < WINDOW_END_HOUR
            stationary = abs(velocity) <= 0.05
            on_street = bounds[0] <= center[0] <= bounds[1] and bounds[2] <= center[1] <= bounds[3]
            qualifies = stationary and on_street and inside
            if qualifies:
                if current_start is None:
                    current_start = ms
                longest_ms = max(longest_ms, ms - current_start)
            else:
                current_start = None
            if first_ms is None:
                first_ms = ms
            last_ms = ms
            previous_ms = ms
            previous_frame = frame
            count += 1
    if count < 2:
        raise ValueError("No complete parking episode")
    if provenance.get("expected_frame_count") != count:
        raise ValueError("Frame count differs from source provenance")
    return {
        "format": "worker-night-parking-diagnostic",
        "mode": provenance["mode"],
        "observations_sha256": sha256(observations_path),
        "provenance_sha256": sha256(provenance_path),
        "frame_count": count,
        "frame_rate_hz": FRAME_RATE,
        "first_utc_epoch_ms": first_ms,
        "last_utc_epoch_ms": last_ms,
        "timezone": provenance["timezone"],
        "longest_continuous_qualifying_ms": longest_ms,
        "observed_duration_over_thirty_minutes": longest_ms > LIMIT_MS if device_class == "qualifying_nonmotor_vehicle" else None,
        "device_class": device_class,
        "parking_activity_annotation": parking["activity_annotation"],
        "physical_or_legal_acceptance": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(args.observations, args.provenance)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
