"""Independent, saved-source audit of the three 80 mph comparison cases.

This checks comparison isolation and source integrity. It never declares a legal
outcome from a requested speed or a sampled maximum.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from speed_measurements import analyze


SUFFIXES = ("source_verified_below_80", "source_verified_at_80", "source_verified_above_80")
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
FIXED_CONFIG = ("law_id", "cell_id", "actor", "duration_s", "fps", "camera_plan", "weather")
FIXED_CONTEXT = ("native_map_id", "road_id", "lane_id", "route_source", "alley_source",
                 "access_aisle_source", "road_authority_source", "subject_blueprint_id")


def _read(path):
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError("Exactly three comparison attempts required")
    records = []
    for attempt in map(Path, attempts):
        config = _read(attempt / "config.json")
        context = _read(attempt / "road_context.json")
        case_id = config.get("selected_case_id", "")
        if not any(case_id.endswith("__" + suffix) for suffix in SUFFIXES):
            raise ValueError("Unexpected exact comparison case: " + str(case_id))
        for name in FIXED_CONFIG:
            if config.get(name) is None:
                raise ValueError("Missing fixed config condition: " + name)
        for name in FIXED_CONTEXT:
            if context.get(name) is None:
                raise ValueError("Missing fixed road condition: " + name)
        if config["fps"] != 20 or config["duration_s"] <= 0:
            raise ValueError("Invalid common capture contract")
        target = config.get("requested_speed_mph")
        if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target):
            raise ValueError("Missing finite requested speed")
        source_hashes = {}
        for camera in CAMERAS:
            path = attempt / camera
            if not path.is_file() or not path.stat().st_size:
                raise ValueError("Missing source camera: " + camera)
            source_hashes[camera] = _hash(path)
        report = analyze(attempt)
        source_hashes.update(report["sources"])
        records.append({"case_id": case_id, "target_mph": float(target),
                        "sampled_peak_mph": report["peak_sample"]["speed_mph"],
                        "sampled_peak_over_80": report["sampled_peak_greater_than_80_mph"],
                        "fixed_config": {name: config[name] for name in FIXED_CONFIG},
                        "fixed_context": {name: context[name] for name in FIXED_CONTEXT},
                        "sources": source_hashes})
    by_suffix = {}
    for record in records:
        suffix = next(s for s in SUFFIXES if record["case_id"].endswith("__" + s))
        if suffix in by_suffix:
            raise ValueError("Duplicate comparison case: " + suffix)
        by_suffix[suffix] = record
    if set(by_suffix) != set(SUFFIXES):
        raise ValueError("Missing comparison case")
    ordered = [by_suffix[s] for s in SUFFIXES]
    prefixes = {r["case_id"].rsplit("__", 1)[0] for r in ordered}
    if len(prefixes) != 1:
        raise ValueError("Mixed assignment comparison")
    for name in ("fixed_config", "fixed_context"):
        if any(r[name] != ordered[0][name] for r in ordered[1:]):
            raise ValueError("Comparison fixed conditions differ: " + name)
    targets = [r["target_mph"] for r in ordered]
    if not (targets[0] < 80 == targets[1] < targets[2]):
        raise ValueError("Requested speed comparison does not bracket 80 mph")
    return {"format": "worker-speed-comparison-audit", "comparison_id": "absolute_80_mph_boundary",
            "case_ids": [r["case_id"] for r in ordered], "records": ordered,
            "fixed_conditions_checked": list(FIXED_CONFIG) + list(FIXED_CONTEXT),
            "deliberate_difference": "requested speed target across exact 80 mph boundary",
            "between_sample_peak": "unresolved", "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = audit(args.attempt)
    Path(args.output).write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
