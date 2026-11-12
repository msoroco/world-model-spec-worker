"""Stage the uncovered railroad reference as a selected delivery construction."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__rail_reference"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = ROOT / "inputs" / HERE.name / "assignment.json"
    assignment = json.loads(frozen.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    draft_path = HERE / "draft-statutory-execution-manifest.json"
    draft = json.loads(draft_path.read_text())
    law = assignment["law_record"]["text"]
    assert assignment["assignment_id"] == HERE.name
    assert "railroad grade crossing" in law and "one-way highway" in law
    assert any(gap["id"] == "railroad_and_traversal"
               for gap in plan["evidence_review"]["gaps"])
    accepted = assignment["local_snapshot"]["memberships"]["full-train"]
    assert len(accepted) == 3 and all("100-" in row["case_id"] for row in accepted)
    assert not any("rail" in row["case_id"].lower() for row in accepted)
    entry = copy.deepcopy(next(row for row in draft["cases"] if row["case_id"] == CASE))
    assert len(entry["candidates"]) == 3
    for candidate in [entry, *entry["candidates"]]:
        assert sha(HERE / candidate["construction"]) == candidate["construction_sha256"]
    entry["kind"] = "delivery"
    entry["preparation_status"] = "selected_stage_needs_current_proofs"
    manifest = {"format": draft["format"], "assignment_id": HERE.name,
                "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
                "status": "partial_selected_stage",
                "selection_review": {
                    "law_input_sha256": sha(frozen),
                    "case_plan_sha256": sha(HERE / "case-plan.json"),
                    "draft_manifest_sha256": sha(draft_path),
                    "selected_case_id": CASE,
                    "reason": "Railroad approach alternative has no accepted source-backed coverage in the export; preserve the 101/100/99-foot intersection originals.",
                    "accepted_intersection_recording_ids": [row["recording_id"] for row in accepted],
                    "accepted_railroad_equivalence_receipt": None,
                    "source_review": "Frozen NRS 484B.213(2)(b),(3), assignment membership rows and case-plan evidence review",
                    "physical_or_legal_acceptance_claimed": False},
                "cases": [entry]}
    output = HERE / "selected-rail-reference-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case_id": CASE, "candidate_count": 4,
                      "manifest_sha256": sha(output), "delivery_accepted": False}))


if __name__ == "__main__":
    main()
