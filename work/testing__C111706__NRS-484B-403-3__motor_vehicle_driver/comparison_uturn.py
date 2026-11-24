"""Independent source-bound comparison checks for the two planned U-turn pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_uturn import analyze_native


class ComparisonError(ValueError):
    pass


ASSIGNMENT = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver"
PAIRS = {
    "intersection_exception_location": frozenset((
        ASSIGNMENT + "__intersection_vehicle_near",
        ASSIGNMENT + "__approach_before_intersection")),
    "surrounding_vehicle_context": frozenset((
        ASSIGNMENT + "__intersection_vehicle_near",
        ASSIGNMENT + "__intersection_vehicle_far")),
}


def _need(ok, reason):
    if not ok:
        raise ComparisonError(reason)


def _read(path, expected_sha):
    _need(hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha,
          "comparison source hash mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def compare(comparison_id: str, left_site: Path, left_site_sha: str,
            left_native: Path, left_native_sha: str, right_site: Path,
            right_site_sha: str, right_native: Path, right_native_sha: str):
    """Compare sealed authored setup and measured original Native outcomes.

    No physical success or legal classification is inferred from the case name.
    Requiring completed site fields means an unsurveyed draft cannot pass.
    """
    _need(comparison_id in PAIRS,
          "unknown comparison")
    left = _read(left_site, left_site_sha)
    right = _read(right_site, right_site_sha)
    _need(frozenset((left.get("case_id"), right.get("case_id"))) == PAIRS[comparison_id],
          "exact comparison case pair differs")
    for site, site_sha, native_path, native_sha in (
            (left, left_site_sha, left_native, left_native_sha),
            (right, right_site_sha, right_native, right_native_sha)):
        packet = _read(native_path, native_sha)
        _need(packet.get("site_sha256") == site_sha and
              packet.get("map_sha256") == site.get("map_sha256") and
              packet.get("route_sha256") == site.get("route_sha256"),
              "Native site/map/route source binding differs")
    left_result = analyze_native(left_native, expected_case=left["case_id"],
                                 expected_sha256=left_native_sha)
    right_result = analyze_native(right_native, expected_case=right["case_id"],
                                  expected_sha256=right_native_sha)
    _need(left["case_id"] != right["case_id"], "comparison cases must differ")
    _need(left_result["frame_count"] == right_result["frame_count"] == 900,
          "comparison requires complete 900-frame sources")
    common = ("map_sha256", "district_source_sha256", "intersection_boundary_source_sha256",
              "ego_blueprint", "other_blueprint", "weather_sha256", "camera_policy_sha256",
              "other_route_sha256")
    for key in common:
        _need(left.get(key) and left.get(key) == right.get(key),
              f"fixed comparison source differs: {key}")
    _need(left_result["district_source_sha256"] == right_result["district_source_sha256"] ==
          left["district_source_sha256"], "Native district/source mismatch")
    _need(left_result["intersection_boundary_source_sha256"] ==
          right_result["intersection_boundary_source_sha256"] ==
          left["intersection_boundary_source_sha256"], "Native boundary/source mismatch")
    if comparison_id == "intersection_exception_location":
        _need(left.get("other_start_tick") == right.get("other_start_tick") is not None,
              "other-vehicle timing changed")
        _need(left.get("ego_route_sha256") and right.get("ego_route_sha256") and
              left["ego_route_sha256"] != right["ego_route_sha256"],
              "ego path difference missing")
        _need(bool(left_result["whole_body_inside_intersection_frames"]) !=
              bool(right_result["whole_body_inside_intersection_frames"]),
              "original intersection footprint distinction missing")
    else:
        _need(left.get("ego_route_sha256") and
              left["ego_route_sha256"] == right.get("ego_route_sha256"),
              "ego path changed in surrounding-vehicle pair")
        _need(isinstance(left.get("other_start_tick"), int) and
              isinstance(right.get("other_start_tick"), int) and
              left["other_start_tick"] != right["other_start_tick"],
              "other-vehicle timing difference missing")
    return {"comparison_id": comparison_id, "left_case": left["case_id"],
            "right_case": right["case_id"],
            "left_native_sha256": left_native_sha, "right_native_sha256": right_native_sha,
            "fixed_sources_checked": list(common),
            "observed_whole_body_inside_intersection_frames": [
                len(left_result["whole_body_inside_intersection_frames"]),
                len(right_result["whole_body_inside_intersection_frames"])],
            "observed_minimum_other_vehicle_center_distance_m": [
                left_result["minimum_other_vehicle_center_distance_m"],
                right_result["minimum_other_vehicle_center_distance_m"]],
            "legal_interpretation": "unresolved_review"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    for side in ("left", "right"):
        parser.add_argument(f"--{side}-site", type=Path, required=True)
        parser.add_argument(f"--{side}-site-sha256", required=True)
        parser.add_argument(f"--{side}-native", type=Path, required=True)
        parser.add_argument(f"--{side}-native-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.comparison, args.left_site, args.left_site_sha256,
                     args.left_native, args.left_native_sha256,
                     args.right_site, args.right_site_sha256,
                     args.right_native, args.right_native_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
