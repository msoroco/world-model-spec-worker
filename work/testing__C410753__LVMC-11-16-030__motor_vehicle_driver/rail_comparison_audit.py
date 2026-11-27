"""Independent CPU comparison of saved original railway observations.

This checks whether the planned experimental contrasts were actually observed.
It never decides the legal speed or visibility question.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rail_native_capture import CAMERAS
from rail_saved_measurement import _source, verify_saved


EXPECTED = {
    "obscured_14mph": ("below", True, False, False, False),
    "obscured_15mph": ("at", True, False, False, False),
    "obscured_16mph": ("above", True, False, False, False),
    "clear_view_16mph": ("above", False, False, False, False),
    "flagman_16mph": ("above", True, True, False, False),
    "signal_nonwarning_16mph": ("above", True, False, True, False),
    "signal_warning_16mph": ("above", True, False, False, True),
}


def audit_comparison(plan, comparison_id, saved):
    """Require source-complete exact cases, fixed site/profile, and realized contrast."""
    if not isinstance(plan, dict) or not isinstance(saved, dict):
        raise ValueError("rail comparison plan or saved observations missing")
    comparisons = {entry["comparison_id"]: entry for entry in plan["comparisons"]}
    if comparison_id not in comparisons:
        raise ValueError("unknown railway comparison")
    cases = comparisons[comparison_id]["case_ids"]
    if len(cases) < 2 or set(saved) != set(cases):
        raise ValueError("exact railway comparison case set differs")
    sites = set()
    for case_id in cases:
        key = case_id.removeprefix(plan["assignment_id"] + "__")
        if case_id != plan["assignment_id"] + "__" + key or key not in EXPECTED:
            raise ValueError("unknown exact railway case")
        row = saved[case_id]
        if (row.get("case_id") != case_id or row.get("source_complete") is not True or
                row.get("original_frame_count") != 900 or
                len(row.get("camera_views", [])) != len(CAMERAS) or
                set(row["camera_views"]) != set(CAMERAS) or
                row.get("legal_conclusion") is not None):
            raise ValueError("rail comparison original source admission differs")
        observation = row.get("observation")
        if not isinstance(observation, dict) or observation.get("legal_speed_verdict") is not None:
            raise ValueError("rail comparison original measurement missing")
        sites.add(observation.get("review_source_sha256"))
        exceptions = observation.get("exceptions")
        if not isinstance(exceptions, dict):
            raise ValueError("rail comparison exception measurements missing")
        actual = (observation.get("speed_boundary_relation_observed"),
                  observation.get("any_required_sight_ray_obstructed"),
                  exceptions.get("on_duty_flagman_observed"),
                  exceptions.get("clearly_visible_nonwarning_signal_observed"),
                  exceptions.get("clearly_visible_warning_signal_observed"))
        if actual != EXPECTED[key]:
            raise ValueError("planned railway contrast not observed: " + key)
    if (len(sites) != 1 or not isinstance(next(iter(sites)), str) or
            len(next(iter(sites))) != 64 or
            any(character not in "0123456789abcdef" for character in next(iter(sites)))):
        raise ValueError("rail comparison reviewed site differs")
    return {"comparison_id": comparison_id, "case_ids": cases,
            "review_source_sha256": next(iter(sites)),
            "original_sources_admitted": True,
            "planned_contrast_observed": True,
            "physical_completion_confirmed": False,
            "legal_conclusion": None}


def audit_attempts(plan, comparison_id, attempt_paths):
    """Reopen sealed original attempts before comparing their observations."""
    if not isinstance(attempt_paths, dict):
        raise ValueError("exact railway attempt mapping missing")
    saved = {}
    for case_id, path in attempt_paths.items():
        root = Path(path).resolve()
        receipt_path = root / "native-rail-receipt.json"
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise ValueError("original railway receipt missing: " + case_id)
        receipt = json.loads(receipt_path.read_text())
        packet = json.loads(_source(root, receipt.get("packet")).read_text())
        saved[case_id] = verify_saved(root, packet, case_id)
    return audit_comparison(plan, comparison_id, saved)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempts", type=Path, required=True,
                        help="JSON map of exact case IDs to original attempt directories")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    attempts = json.loads(args.attempts.read_text())
    result = audit_attempts(plan, args.comparison, attempts)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
