"""Reproduce the frozen right/left statutory coverage dependency."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ACTOR = "cycle_or_scooter_operator"
LAW = "LVMC-11-40-080"
ALTERNATIVES = (("no_left_turn", "C102581", "left_turn"),
                ("no_right_turn", "C103714", "right_turn"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def verify_runtime_rejection(original: dict, catalog_path: Path,
                             batch: dict, cell_id: str, proposed_id: str) -> str:
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.branch_coverage import assignments
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                     prefix="c104538-frozen-binding-") as name:
        temp = Path(name)
        target = temp / "inputs/coverage/candidate-cells.json"
        target.parent.mkdir(parents=True)
        shutil.copyfile(catalog_path, target)
        original_path = temp / "inputs" / ROOT.name / "assignment.json"
        original_path.parent.mkdir(parents=True)
        original_path.write_text(json.dumps(original) + "\n")
        proposal_path = temp / "work" / proposed_id / "assignment.json"
        proposal_path.parent.mkdir(parents=True)
        proposal_path.write_text(json.dumps({**original, "assignment_id": proposed_id,
                                             "cell_id": cell_id}) + "\n")
        coverage_path = temp / "work/_shared/branch-coverage.json"
        coverage_path.parent.mkdir(parents=True)
        coverage_path.write_text(json.dumps({"additional_bindings": [{
            "assignment_id": proposed_id, "original_assignment_id": ROOT.name,
            "original_cell_incompatibility": "U-turn cell does not show a right/left turn",
            "binding_reason": "test eligibility only"}]}) + "\n")
        try:
            assignments(temp, {**batch, "full_branch_coverage_required": True})
        except ValueError as error:
            if str(error) != "Ineligible supplemental binding":
                raise
            return str(error)
    raise ValueError("Frozen runtime unexpectedly accepted supplemental binding")


def main() -> None:
    paths = {
        "assignment": REPO / "inputs" / ROOT.name / "assignment.json",
        "witnesses": REPO / "inputs" / ROOT.name / "witnesses.json",
        "branch_sources": REPO / "inputs/coverage/branch-sources.json",
        "candidate_catalog": REPO / "inputs/coverage/candidate-cells.json",
        "batch": REPO / "batch.json",
        "runtime_eligibility": REPO / "runtime/scenario_pipeline/worker_exchange/branch_coverage.py",
        "eligibility_test": ROOT / "supplemental-eligibility-proof.json",
        "staged_cases": ROOT / "staged-turn-cells/staging-execution-manifest.json",
    }
    assignment = load(paths["assignment"])
    witness = load(paths["witnesses"])
    sources = load(paths["branch_sources"])["laws"][LAW]
    catalog = {row["cell_id"]: row for row in load(paths["candidate_catalog"])["cells"]}
    batch = load(paths["batch"])
    tested = load(paths["eligibility_test"])
    staged = load(paths["staged_cases"])
    law_text = assignment["law"]["text"]
    if (assignment["cell_id"] != "C104538" or assignment["cell"]["maneuver"] != "u_turn"
            or assignment["actor"] != ACTOR or sources["law"]["text"] != law_text
            or "no right turn, left turn or U-turn" not in law_text
            or len(witness) != 1 or witness[0]["witness"]["cell"] != "C104538"
            or "U-turn" not in witness[0]["witness"]["branch"]
            or tested["candidate_catalog_sha256"] != sha(paths["candidate_catalog"])
            or tested["runtime_source_sha256"] != sha(paths["runtime_eligibility"])):
        raise ValueError("Frozen law, assignment, witness or eligibility source differs")
    assigned_law = []
    for aid in batch["assignments"]:
        input_path = REPO / "inputs" / aid / "assignment.json"
        if input_path.is_file() and load(input_path).get("law_id") == LAW:
            assigned_law.append(aid)
    if assigned_law != [ROOT.name]:
        raise ValueError("Frozen batch has another assigned restricted-turn cell")
    staged_ids = {entry["case_id"] for entry in staged["cases"]}
    tested_results = {item["cell_id"]: item for item in tested["results"]}
    rows = []
    for branch, cell_id, maneuver in ALTERNATIVES:
        cell = catalog[cell_id]
        expected_id = f"training__{cell_id}__{LAW}__{ACTOR}"
        case_ids = sorted(cid for cid in staged_ids if cid.startswith(expected_id + "__"))
        if (cell["layout"] != "hill_crest" or cell["maneuver"] != maneuver or
                cell["control"] != "turn_prohibition_device" or
                ACTOR in cell["candidate_ego_parties"] or cell["allocated_sets"] or
                len(case_ids) != 2 or tested_results[cell_id]["accepted"] is not False or
                tested_results[cell_id]["error"] != "Ineligible supplemental binding"):
            raise ValueError("Frozen alternative changed or unexpectedly became eligible: " + cell_id)
        runtime_error = verify_runtime_rejection(
            assignment, paths["candidate_catalog"], batch, cell_id, expected_id)
        rows.append({"branch": branch, "cell_id": cell_id, "maneuver": maneuver,
                     "candidate_ego_parties": cell["candidate_ego_parties"],
                     "allocated_sets": cell["allocated_sets"],
                     "exact_staged_case_ids": case_ids,
                     "runtime_rejection": runtime_error,
                     "selectable_in_frozen_batch": False})
    report = {"format": "c104538-frozen-right-left-dependency-v1",
              "audit_source_sha256": sha(Path(__file__)),
              "runtime_retested_in_isolated_repository": True,
              "law_id": LAW, "assignment_id": ROOT.name,
              "statutory_sign_directions": ["right", "left", "U-turn"],
              "frozen_assignment_maneuver": "u_turn",
              "frozen_witness_branch": witness[0]["witness"]["branch"],
              "same_law_batch_assignments": assigned_law,
              "alternatives": rows,
              "within_cell_cpu_alternative": "no-right/no-left sign variants are negative governing controls for an intended U-turn; they cannot establish a prohibited right/left turn",
              "minimum_external_dependency": "a source-authorized right/left cell assignment with cycle_or_scooter_operator eligibility and set allocation, or a corrected frozen catalog and batch authorization",
              "physical_or_legal_acceptance_claimed": False,
              "source_sha256": {name: sha(path) for name, path in paths.items()}}
    output = ROOT / "frozen-right-left-dependency.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"alternatives_rejected": len(rows),
                      "same_law_batch_assignments": len(assigned_law),
                      "report_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
