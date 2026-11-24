"""Exact-case saved measurements for NRS 484B.253.

This describes observed events; it does not decide immediate hazard, yielding,
signal requirements, right-of-way, or any legal outcome.
"""

import argparse
import hashlib
import json
from pathlib import Path

from saved_left_turn import ASSIGNMENT_ID, process


BRANCHES = {
    "inside_yield": (0, "measure_initial_within"),
    "inside_no_yield": (0, "measure_initial_within"),
    "approaching_yield": (1, "measure_approaching"),
    "approaching_no_yield": (1, "measure_approaching"),
    "signal_given": (2, "measure_permission"),
    "signal_omitted": (2, "measure_permission"),
    "reciprocal_yield": (3, "measure_reciprocal"),
    "reciprocal_no_yield": (3, "measure_reciprocal"),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _first(rows, predicate):
    return next((row["frame"] for row in rows if predicate(row)), None)


def measure_initial_within(rows):
    return {
        "ego_full_body_inside_first_frame": _first(rows, lambda r: r["ego"]["full_body_inside"]),
        "opponent_any_body_inside_first_frame": _first(rows, lambda r: r["opponent"]["any_vertex_inside"]),
        "opponent_full_body_inside_first_frame": _first(rows, lambda r: r["opponent"]["full_body_inside"]),
        "ego_commit_first_frame": _first(rows, lambda r: r["ego_turn_committed"]),
        "opponent_clear_first_frame": _first(rows, lambda r: r["opponent_cleared"]),
        "opposite_heading_cosine_by_frame": [[r["frame"], r["heading_cosine"]] for r in rows],
        "ego_braking_by_frame": [[r["frame"], r["ego_braking"]] for r in rows],
    }


def measure_approaching(rows):
    return {
        "opponent_outside_first_frame": _first(rows, lambda r: not r["opponent"]["any_vertex_inside"]),
        "opponent_inside_first_frame": _first(rows, lambda r: r["opponent"]["any_vertex_inside"]),
        "opponent_speed_mps_by_frame": [[r["frame"], r["opponent_speed_mps"]] for r in rows],
        "ego_commit_first_frame": _first(rows, lambda r: r["ego_turn_committed"]),
        "ego_braking_by_frame": [[r["frame"], r["ego_braking"]] for r in rows],
        "immediate_hazard_judgment": "unresolved",
    }


def measure_permission(rows):
    return {
        "opponent_clear_first_frame": _first(rows, lambda r: r["opponent_cleared"]),
        "ego_commit_first_frame": _first(rows, lambda r: r["ego_turn_committed"]),
        "left_signal_by_frame": [[r["frame"], r["ego_signal_left"]] for r in rows],
        "ego_braking_by_frame": [[r["frame"], r["ego_braking"]] for r in rows],
        "signal_when_and_as_required": "unresolved",
    }


def measure_reciprocal(rows):
    return {
        "initial_opponent_clear_first_frame": _first(rows, lambda r: r["opponent_cleared"]),
        "ego_commit_first_frame": _first(rows, lambda r: r["ego_turn_committed"]),
        "opponent_speed_mps_by_frame": [[r["frame"], r["opponent_speed_mps"]] for r in rows],
        "ego_signal_by_frame": [[r["frame"], r["ego_signal_left"]] for r in rows],
        "later_opponent_identity": "unresolved_without_distinct_source_actor",
    }


METHODS = {name: globals()[name] for _, name in BRANCHES.values()}


def finalize(*, case_id, attempt):
    """Read one sealed acquisition and return a source-bound case observation."""
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
    if suffix not in BRANCHES:
        raise ValueError("case has no selected statutory requirement")
    attempt = Path(attempt)
    map_path = attempt / "original-map.json"
    trace_path = attempt / "original-trace.jsonl"
    receipt_path = attempt / "acquisition-receipt.json"
    for name in ("original-map.json", "original-trace.jsonl", "acquisition-receipt.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    measured = process(case_id=case_id, map_path=map_path,
                       trace_path=trace_path, receipt_path=receipt_path)
    index, method = BRANCHES[suffix]
    sources = {name: _sha(attempt / name) for name in
               ("original-map.json", "original-trace.jsonl", "acquisition-receipt.json")}
    if (attempt / "original-frame-map.json").is_file():
        sources["original-frame-map.json"] = _sha(attempt / "original-frame-map.json")
    observations = METHODS[method](measured["frames"])
    core_sources = {name: sources[name] for name in
                    ("original-map.json", "original-trace.jsonl", "acquisition-receipt.json")}
    output_key = {0: "initial_within_events", 1: "approaching_events",
                  2: "permission_events", 3: "reciprocal_events"}[index]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "selected_disposition_index": index, "method": method,
            "source_hashes": sources, "observations": observations,
            "measurements": {output_key: {"method": method, "value": observations,
                                          "sources": core_sources}},
            "original_frame_count": len(measured["frames"]),
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    case_id = args.case
    if case_id is None:
        receipt = Path(args.attempt) / "acquisition-receipt.json"
        if not receipt.is_file():
            raise ValueError("Missing required source: acquisition-receipt.json")
        case_id = json.loads(receipt.read_text(encoding="utf-8"))["case_id"]
    result = finalize(case_id=case_id, attempt=args.attempt)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
