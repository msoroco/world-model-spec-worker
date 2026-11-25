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
from door_interaction import Point, segment_distance


def _read_hashed(path: Path, expected_sha256: str) -> dict:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("clearance source hash mismatch")
    return json.loads(data)


def _polygon_gap(first: list, second: list) -> float:
    """Minimum source-envelope/body gap from original world XY vertices."""
    def points(vertices):
        if not isinstance(vertices, list) or len(vertices) < 2:
            raise ValueError("original clearance outline needs two vertices")
        result = []
        for value in vertices:
            if (not isinstance(value, list) or len(value) != 2 or
                    any(type(item) not in (int, float) or not math.isfinite(item)
                        for item in value)):
                raise ValueError("original clearance vertex is invalid")
            result.append(Point(*value))
        return result
    a, b = points(first), points(second)
    def contains(point, polygon):
        inside = False
        for i, start in enumerate(polygon):
            end = polygon[(i + 1) % len(polygon)]
            if (start.y > point.y) != (end.y > point.y):
                crossing_x = (end.x - start.x) * (point.y - start.y) / (
                    end.y - start.y) + start.x
                if point.x < crossing_x:
                    inside = not inside
        return inside
    if (len(a) >= 3 and len(b) >= 3 and
            (contains(a[0], b) or contains(b[0], a))):
        return 0.0
    return min(segment_distance(a[i], a[i + 1], b[j], b[j + 1])
               for i in range(len(a) - 1) for j in range(len(b) - 1))


def _source_levels(source: dict, survey: dict, clearance_path: Path) -> tuple[dict, dict]:
    refs = source.get("source_refs")
    if not isinstance(refs, list) or len(refs) != 3:
        raise ValueError("three original clearance source refs are required")
    levels = {}
    frames = {}
    seen_sources = set()
    case_prefix = "testing__C102642__NRS-484B-153-2__motor_vehicle_driver__"
    for ref in refs:
        if not isinstance(ref, dict) or ref.get("level") not in (
                "below", "inside", "above") or ref["level"] in levels:
            raise ValueError("clearance source level is duplicated or unknown")
        path = Path(ref.get("path", ""))
        if not path.is_absolute():
            path = clearance_path.parent / path
        if not path.is_file() or not isinstance(ref.get("sha256"), str):
            raise ValueError("original clearance source file is missing")
        if ref["sha256"] in seen_sources:
            raise ValueError("clearance levels must use distinct original frames")
        seen_sources.add(ref["sha256"])
        sample = _read_hashed(path, ref["sha256"])
        if sample.get("source_kind") != "native_original_clearance_frame":
            raise ValueError("original Native clearance frame is required")
        if (sample.get("map_sha256") != survey["map_sha256"] or
                sample.get("loading_site_id") != survey["loading_site_id"]):
            raise ValueError("original clearance frame does not join surveyed site")
        case_id = sample.get("case_id")
        if (case_id != ref.get("case_id") or not isinstance(case_id, str) or
                not case_id.startswith(case_prefix) or
                not case_id[len(case_prefix):]):
            raise ValueError("original clearance frame does not join assignment case")
        if not sample.get("source_observation_id"):
            raise ValueError("original clearance frame observation identity is missing")
        if type(sample.get("frame_id")) is not int or sample["frame_id"] < 0:
            raise ValueError("original clearance frame identity is missing")
        if sample.get("door_open") is not True or not (
                type(sample.get("passing_speed_mps")) in (int, float) and
                math.isfinite(sample["passing_speed_mps"]) and
                sample["passing_speed_mps"] > 0):
            raise ValueError("door and moving traffic must overlap in source frame")
        levels[ref["level"]] = _polygon_gap(
            sample.get("door_vertices_xy"), sample.get("passing_body_vertices_xy"))
        frames[ref["level"]] = {"case_id": case_id,
                                "source_observation_id": sample["source_observation_id"],
                                "frame_id": sample["frame_id"],
                                "sha256": ref["sha256"]}
    if set(levels) != {"below", "inside", "above"}:
        raise ValueError("three original clearance levels are required")
    return levels, frames


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
    levels, frames = _source_levels(source, survey, clearance_path)
    declared = source.get("door_body_gap_levels_m")
    if not isinstance(declared, dict) or set(declared) != set(levels):
        raise ValueError("three declared clearance levels are required")
    if any(type(declared[key]) not in (int, float) or not math.isfinite(declared[key]) or
           abs(declared[key] - levels[key]) > 1e-6 for key in levels):
        raise ValueError("declared clearance differs from original vertices")
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
        "source_frames": frames,
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
