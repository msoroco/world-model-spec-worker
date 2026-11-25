"""Expand the exact statute into a source-hashed, still provisional case matrix."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = ROOT / "inputs/coverage/branch-sources.json"
KINDS = (
    "nearest_view_response", "nearest_view_uninterrupted",
    "marked_stop_line_response", "marked_stop_line_uninterrupted",
    "near_side_marked_crosswalk_response", "near_side_marked_crosswalk_uninterrupted",
    "near_side_sidewalk_derived_crosswalk_response",
    "near_side_sidewalk_derived_crosswalk_uninterrupted",
    "approaching_phase_probe", "later_history_probe", "nearest_view_stopped",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    statute = json.loads(SOURCE.read_text())["laws"][assignment["law_id"]]
    if statute["law"]["text"] != assignment["law"]["text"]:
        raise ValueError("full statutory source differs from assignment")
    members = assignment["local_snapshot"]["memberships"]["demo-test"]
    accepted = {row["case_id"]: row["recording_id"] for row in members
                if row.get("status") == "accepted"}
    expected = {ASSIGNMENT + "__" + kind for kind in KINDS}
    if set(accepted) != expected:
        raise ValueError("frozen accepted case inventory changed")

    def cases(*kinds: str) -> list[str]:
        ids = [ASSIGNMENT + "__" + kind for kind in kinds]
        if not set(ids) <= expected:
            raise ValueError("matrix references unknown accepted case")
        return ids

    common = "one-way-to-two-way intersection, motor vehicle, original sign and through highway"
    branches = [
        {"branch_id": "nearest_view_no_line_or_crosswalk", "statutory_clause": "point nearest the intersection where the driver has a view", "case_ids": cases("nearest_view_response", "nearest_view_uninterrupted", "nearest_view_stopped"), "fixed_conditions": common + "; yield sign, no marked stop line or near-side crosswalk", "deliberate_differences": "response versus uninterrupted versus stopped approach"},
        {"branch_id": "marked_stop_line_priority", "statutory_clause": "at a clearly marked stop line", "case_ids": cases("marked_stop_line_response", "marked_stop_line_uninterrupted"), "fixed_conditions": common + "; marked stop line present", "deliberate_differences": "response versus uninterrupted approach"},
        {"branch_id": "near_side_marked_crosswalk_priority", "statutory_clause": "before entering the crosswalk on the near side", "case_ids": cases("near_side_marked_crosswalk_response", "near_side_marked_crosswalk_uninterrupted"), "fixed_conditions": common + "; no stop line, marked near-side crosswalk", "deliberate_differences": "response versus uninterrupted approach"},
        {"branch_id": "near_side_sidewalk_crosswalk_priority", "statutory_clause": "before entering the crosswalk on the near side", "case_ids": cases("near_side_sidewalk_derived_crosswalk_response", "near_side_sidewalk_derived_crosswalk_uninterrupted"), "fixed_conditions": common + "; no stop line, sidewalk-derived near-side crosswalk", "deliberate_differences": "response versus uninterrupted approach"},
        {"branch_id": "yield_slowed_or_stopped", "statutory_clause": "in the event of a yield sign, slowed or stopped", "case_ids": cases("nearest_view_response", "nearest_view_uninterrupted", "nearest_view_stopped"), "fixed_conditions": common + "; yield sign and nearest-view location", "deliberate_differences": "measured slowing, stopping or uninterrupted motion; no invented legal speed cutoff"},
        {"branch_id": "occupied_or_approaching_traffic", "statutory_clause": "entered the intersection or approaching so closely", "case_ids": cases("nearest_view_response", "approaching_phase_probe", "later_history_probe"), "fixed_conditions": common + "; through-highway priority and ego crossing geometry", "deliberate_differences": "through vehicle already inside versus approaching before entry versus later history"},
        {"branch_id": "across_or_within_history", "statutory_clause": "during the time such driver is moving across or within", "case_ids": cases("nearest_view_response", "approaching_phase_probe", "later_history_probe"), "fixed_conditions": common + "; same intersection and through highway", "deliberate_differences": "temporal overlap of original through-vehicle and ego histories"},
    ]
    all_core = {ident for row in branches for ident in row["case_ids"]}
    if all_core != expected or any(len(row["case_ids"]) < 2 for row in branches):
        raise ValueError("accepted core cases or comparisons omitted")
    exceptions = [
        {"branch_id": "police_officer_controls_traffic", "statutory_clause": "Except when traffic is being controlled by a police officer", "candidate_cell_id": "C158170", "candidate_control": "police_officer", "status": "source_and_binding_review_pending", "needed_comparison": "officer actually controls traffic versus sign-governed approach"},
        {"branch_id": "signal_controls_traffic", "statutory_clause": "or a traffic-control signal", "candidate_cell_id": "C158196", "candidate_control": "traffic_light", "status": "source_and_binding_review_pending", "needed_comparison": "signal actually controls traffic versus sign-governed approach"},
        {"branch_id": "stop_sign_and_stop_action", "statutory_clause": "driver of a vehicle shall stop or yield", "candidate_cell_id": "C158190", "candidate_control": "stop_sign", "status": "source_and_binding_review_pending", "needed_comparison": "stop-sign action versus yield-sign slowing/stopping at matched reference location"},
    ]
    catalog = json.loads((ROOT / "inputs/coverage/candidate-cells.json").read_text())
    by_id = {row["cell_id"]: row for row in catalog["cells"]}
    for row in exceptions:
        cell = by_id[row["candidate_cell_id"]]
        if (cell["layout"] != assignment["cell"]["layout"] or
                cell["maneuver"] != assignment["cell"]["maneuver"] or
                cell["control"] != row["candidate_control"] or
                assignment["actor"] not in cell.get("candidate_ego_parties",
                                                    cell.get("grounding_by_party", {}))):
            raise ValueError("proposed exception cell is not compatible")
    matrix = {"format": "c158208-statutory-matrix-draft", "assignment_id": ASSIGNMENT,
              "status": "source_review_and_original_measurement_pending",
              "law_source": {"path": str(SOURCE.relative_to(ROOT)), "sha256": sha(SOURCE)},
              "candidate_cell_source": {"path": "inputs/coverage/candidate-cells.json",
                                        "sha256": sha(ROOT / "inputs/coverage/candidate-cells.json")},
              "accepted_recordings": accepted, "branches": branches,
              "additional_binding_candidates": exceptions,
              "required_original_observations": [
                  "proper stop or yield sign erected and governing the approach",
                  "stop line presence and the statutory stopping-reference hierarchy",
                  "near-side marked or sidewalk-derived crosswalk presence",
                  "actual police-officer or traffic-signal control, not mere device presence",
                  "through-highway status and original vehicle occupancy or approach history",
                  "ego slowing or stopping and across-or-within time history",
                  "immediate hazard and right-of-way remain unresolved judgment calls"],
              "limitations": ["Metadata records acceptance but does not prove physical sufficiency.",
                              "Original site, camera pixels and control authority remain unreviewed.",
                              "No exception or stop-sign case is selected without its own compatible source and binding."]}
    output = HERE / "statutory-matrix.draft.json"
    output.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")
    return {"branches": len(branches), "additional_binding_candidates": len(exceptions),
            "accepted_case_ids": len(expected), "matrix_sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
