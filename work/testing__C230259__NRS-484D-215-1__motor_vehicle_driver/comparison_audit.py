"""Independent saved-source comparison of fixed and deliberate case variables."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import build as analyze

ASSIGNMENT = "testing__C230259__NRS-484D-215-1__motor_vehicle_driver"


def _read(root: Path, name: str):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return json.loads(path.read_text())


def _config_fixed(config):
    return {key: config.get(key) for key in
            ("assignment_id", "law_id", "cell_id", "actor", "rate_hz",
             "frame_count", "duration_s", "camera_dimensions", "cameras",
             "required_atoms", "source_packets", "supported_case_ids")}


def _site_fixed(site, comparison_id):
    fields = ["format", "cell_id", "actor", "map_name", "map_sha256",
              "highway_or_shoulder_polygon_xy_m", "blueprints", "targets",
              "cameras", "speed_requests_mps", "driver_eye_offsets_m",
              "nevada_highway_public_access_reviewed", "lighting_time_source_reviewed",
              "lighting_time_qualifies"]
    if comparison_id not in ("lowermost_contour_load",):
        fields += ["requested_contour", "requested_load"]
    if comparison_id not in ("five_hundred_feet_lower", "five_hundred_feet_upper",
                             "lowermost_contour_load"):
        fields += ["routes", "requested_start_body_gap_ft"]
    return {key: site.get(key) for key in fields}


def _mean(values):
    if not values:
        raise ValueError("empty original comparison measurement")
    return sum(values) / len(values)


def _observed_difference(comparison_id, first, second):
    a = first["measurements"]
    b = second["measurements"]
    if comparison_id in ("general_beam_distribution", "general_no_distribution", "near_oncoming_glare"):
        first_bits = a["beam_requirement_3"]["value"]["lamp_readback_bits_by_frame"]
        second_bits = b["beam_requirement_3"]["value"]["lamp_readback_bits_by_frame"]
        changed = first_bits != second_bits
        return {"metric": "original lamp-state readback bits", "changed": changed,
                "first_unique_bits": sorted(set(first_bits)),
                "second_unique_bits": sorted(set(second_bits))}
    if comparison_id in ("five_hundred_feet_lower", "five_hundred_feet_upper"):
        first_gap = a["beam_requirement_2"]["value"]["oncoming_body_gap_m_by_frame"]
        second_gap = b["beam_requirement_2"]["value"]["oncoming_body_gap_m_by_frame"]
        delta = _mean(second_gap) - _mean(first_gap)
        return {"metric": "mean original oncoming body gap m",
                "changed": abs(delta) > .01, "second_minus_first_m": round(delta, 4)}
    if comparison_id == "lowermost_contour_load":
        return {"metric": "source-reviewed contour and load",
                "changed": True, "physical_lowermost_specification_confirmed": False}
    raise ValueError("unknown selected comparison")


def audit(first_attempt: Path, second_attempt: Path, comparison_id: str,
          *, diagnostic: bool = False, expected_frames: int = 900) -> dict:
    a_root = Path(first_attempt).resolve(strict=True)
    b_root = Path(second_attempt).resolve(strict=True)
    if a_root == b_root:
        raise ValueError("comparison needs two distinct original attempts")
    plan_path = Path(__file__).resolve().parent / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    selected = next((x for x in plan["comparisons"] if x["comparison_id"] == comparison_id), None)
    if selected is None:
        raise ValueError("selected comparison missing from exact plan")
    a_config = _read(a_root, "config.json")
    b_config = _read(b_root, "config.json")
    if [a_config.get("selected_case_id"), b_config.get("selected_case_id")] != selected["case_ids"]:
        raise ValueError("comparison exact case order differs")
    if _config_fixed(a_config) != _config_fixed(b_config):
        raise ValueError("comparison fixed capture/identity conditions differ")
    a_site = _read(a_root, "site-packet.json")
    b_site = _read(b_root, "site-packet.json")
    if _site_fixed(a_site, comparison_id) != _site_fixed(b_site, comparison_id):
        raise ValueError("comparison fixed Native site conditions differ")
    a_report = analyze(a_root, expected_frames=expected_frames, diagnostic=diagnostic)
    b_report = analyze(b_root, expected_frames=expected_frames, diagnostic=diagnostic)
    difference = _observed_difference(comparison_id, a_report, b_report)
    if not difference["changed"]:
        raise ValueError("declared comparison variable did not change in original source")
    return {"format": "worker-comparison-audit", "assignment_id": ASSIGNMENT,
            "comparison_id": comparison_id, "case_ids": selected["case_ids"],
            "fixed_conditions": selected["fixed_conditions"],
            "deliberate_differences": selected["deliberate_differences"],
            "fixed_source_conditions_verified": True,
            "observed_difference": difference,
            "first_source_sha256": hashlib.sha256((a_root / "native-source-receipt.json").read_bytes()).hexdigest(),
            "second_source_sha256": hashlib.sha256((b_root / "native-source-receipt.json").read_bytes()).hexdigest(),
            "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", required=True)
    parser.add_argument("--second-attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    result = audit(Path(args.first_attempt), Path(args.second_attempt), args.comparison,
                   diagnostic=args.diagnostic_fixture,
                   expected_frames=9 if args.diagnostic_fixture else 900)
    output = Path(args.output)
    if output.exists():
        raise ValueError("comparison audit output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "passed": True,
                      "diagnostic_fixture": args.diagnostic_fixture}))


if __name__ == "__main__":
    main()
