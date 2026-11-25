"""Check original physical clearance sources before expanding the door sweep.

The returned levels are engineering probes. They make no finding about legal
interference, and no level is inferred from a diagnostic fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from site_contract import read_packet, validate_site


def _read_hashed(path: Path, expected_sha256: str) -> dict:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("clearance source hash mismatch")
    return json.loads(data)


def validate_sweep_sources(survey_path: Path, survey_sha256: str,
                           clearance_path: Path, clearance_sha256: str) -> dict:
    survey = read_packet(survey_path, survey_sha256)
    sites = {key: validate_site(survey, key) for key in (
        "open_near_overlap", "open_near_clear", "open_far_side",
        "board_near", "alight_near")}
    source = _read_hashed(clearance_path, clearance_sha256)
    if source.get("source_kind") != "original_surveyed_clearance_range":
        raise ValueError("original surveyed clearance range is required")
    for field in ("map_sha256", "loading_site_id", "source_observation_id"):
        if not source.get(field):
            raise ValueError("clearance source identity is missing: " + field)
    if source["map_sha256"] != survey["map_sha256"] or source[
            "loading_site_id"] != survey["loading_site_id"]:
        raise ValueError("clearance source does not join the surveyed site")
    levels = source.get("door_body_gap_levels_m")
    if not isinstance(levels, dict) or set(levels) != {"below", "inside", "above"}:
        raise ValueError("three original clearance levels are required")
    values = [levels[key] for key in ("below", "inside", "above")]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in values):
        raise ValueError("clearance levels must be finite measured values")
    if not values[0] < values[1] < values[2]:
        raise ValueError("clearance levels must be strictly ordered")
    if not source.get("measurement_method") or not source.get("source_refs"):
        raise ValueError("clearance measurement method and source refs are required")
    return {
        "format": "door-physical-sweep-source-preflight",
        "survey_sha256": survey_sha256,
        "clearance_sha256": clearance_sha256,
        "map_sha256": survey["map_sha256"],
        "loading_site_id": survey["loading_site_id"],
        "source_observation_id": source["source_observation_id"],
        "levels_m": levels,
        "selected_cases": sorted(sites),
        "legal_interference": "unresolved_judgment",
        "physical_feasibility": "unverified_until_native_capture",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--survey-sha256", required=True)
    parser.add_argument("--clearance", type=Path, required=True)
    parser.add_argument("--clearance-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_sweep_sources(args.survey, args.survey_sha256,
                                    args.clearance, args.clearance_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
