"""Classify remaining statutory alternatives against the frozen assignment."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ACTOR = "cycle_or_scooter_operator"
BRANCHES = (("no_left_turn", "C102581", "left_turn"),
            ("no_right_turn", "C103714", "right_turn"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(catalog, staged, actor=ACTOR):
    cells = {cell["cell_id"]: cell for cell in catalog["cells"]}
    stage_cases = {case["case_id"]: case for case in staged["cases"]}
    output = []
    for branch, cell_id, maneuver in BRANCHES:
        cell = cells[cell_id]
        if (cell["layout"], cell["maneuver"], cell["control"]) != (
                "hill_crest", maneuver, "turn_prohibition_device"):
            raise ValueError("Frozen alternative cell geometry differs: " + cell_id)
        candidate = f"training__{cell_id}__LVMC-11-40-080__{actor}"
        cases = sorted(key for key in stage_cases if key.startswith(candidate + "__"))
        if len(cases) != 2:
            raise ValueError("Exact staged obey/turn pair missing: " + cell_id)
        eligible = actor in cell["candidate_ego_parties"]
        output.append({"branch": branch, "cell_id": cell_id,
                       "eligible_under_frozen_catalog": eligible,
                       "exact_staged_case_ids": cases,
                       "disposition": "eligible_for_separate_assignment" if eligible else
                                      "reject_supplemental_binding_under_frozen_catalog"})
    return output


def main():
    catalog_path = REPO / "inputs/coverage/candidate-cells.json"
    staged_path = HERE / "staged-turn-cells/staging-execution-manifest.json"
    proof_path = HERE / "supplemental-eligibility-proof.json"
    assignment_path = REPO / "inputs" / HERE.name / "assignment.json"
    catalog = json.loads(catalog_path.read_text())
    staged = json.loads(staged_path.read_text())
    proof = json.loads(proof_path.read_text())
    assignment = json.loads(assignment_path.read_text())
    if (assignment["cell_id"] != "C104538" or assignment["cell"]["maneuver"] != "u_turn" or
            proof["candidate_catalog_sha256"] != sha(catalog_path) or
            proof["nonempty_candidate_ego_parties"] != 0):
        raise ValueError("Frozen assignment/catalog eligibility proof differs")
    alternatives = classify(catalog, staged)
    if any(item["eligible_under_frozen_catalog"] for item in alternatives):
        raise ValueError("Frozen alternative eligibility changed; re-evaluate selection")
    for case in staged["cases"]:
        path = HERE / "staged-turn-cells" / case["construction"]
        if sha(path) != case["construction_sha256"]:
            raise ValueError("Staged exact construction changed")
    electric_preflight_path = HERE / "electric-asset-local-preflight.json"
    electric_preflight = json.loads(electric_preflight_path.read_text())
    if electric_preflight.get("electric_assets_selected") is not False:
        raise ValueError("Electric asset selection changed")
    report = {"format": "c104538-frozen-statutory-alternatives-v1",
              "assignment_id": HERE.name,
              "frozen_cell_maneuver": "u_turn",
              "right_left": alternatives,
              "electric_bicycle": "reviewed_exact_native_asset_source_required",
              "electric_scooter": "reviewed_exact_native_asset_source_required",
              "electric_absence_scope": "local CPU preflight only; no live CARLA inventory checked",
              "selected_delivery_unchanged": True,
              "catalog_sha256": sha(catalog_path),
              "assignment_sha256": sha(assignment_path),
              "staged_manifest_sha256": sha(staged_path),
              "supplemental_eligibility_proof_sha256": sha(proof_path),
              "electric_preflight_sha256": sha(electric_preflight_path),
              "physical_or_legal_acceptance_claimed": False}
    output = HERE / "frozen-alternative-audit.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": True, "right_left_rejected": len(alternatives),
                      "electric_classes_pending_source": 2,
                      "report_sha256": sha(output)}))


if __name__ == "__main__":
    main()
