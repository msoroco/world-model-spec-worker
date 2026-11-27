"""Exercise this proposal through the pinned full-branch validator in isolation."""
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve() / "branch-proposal-validation"
    (root / "inputs" / "coverage").mkdir(parents=True, exist_ok=True)
    (root / "inputs" / AID).mkdir(parents=True, exist_ok=True)
    (root / "work" / "_shared").mkdir(parents=True, exist_ok=True)
    (root / "work" / AID).mkdir(parents=True, exist_ok=True)
    proposal = json.loads((HERE / "proposals" / "branch-coverage-proposal.json").read_text())
    source = json.loads((REPO / "inputs" / "coverage" / "branch-sources.json").read_text())
    write(root / "inputs" / "coverage" / "branch-sources.json", {"laws": {proposal["law_id"]: source["laws"][proposal["law_id"]]}})
    for name in ("assignment.json", "evidence.json"):
        (root / "inputs" / AID / name).write_bytes((REPO / "inputs" / AID / name).read_bytes())
    (root / "work" / AID / "case-plan.json").write_bytes((HERE / "case-plan.json").read_bytes())
    write(root / "work" / AID / "result.json", {"readiness_kind": "new_capture"})
    test_log = root / "work" / AID / "saved-proof.log"
    test_log.write_text("synthetic branch-validator fixture\n", encoding="utf-8")
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = {"cases": [{"case_id": case["case_id"], "post_capture": {
        "command": "recorded-only fixture", "feedback_command": "fixture feedback", "recorded_only": True,
        "test_exit_code": 0, "test_log": "saved-proof.log", "test_log_sha256": sha(test_log)
    }} for case in plan["cases"]]}
    write(root / "work" / AID / "execution-manifest.json", manifest)
    matrix = {"format": "worker-full-branch-coverage", "batch_id": "proposal-validation",
              "laws": {proposal["law_id"]: {"branches": proposal["branches"]}}}
    matrix_path = root / "work" / "_shared" / "branch-coverage.json"
    write(matrix_path, matrix)
    write(root / "work" / "_shared" / "branch-review.json", {
        "coverage_sha256": sha(matrix_path), "missing_branches": [], "unreviewed_candidates": [],
        "review_method": "Isolated exact-law fixture; compare proposal cases and topics to the frozen plan.",
        "candidate_review_method": "Inspect all five pairwise comparisons and six case memberships."})
    batch = {"batch_id": "proposal-validation", "full_branch_coverage_required": True,
             "assignments": {AID: {"input_sha256": sha(root / "inputs" / AID / "assignment.json")}}}
    from worker_exchange.branch_coverage import validate
    result = validate(root, batch, batch["assignments"], require_ready=True)
    assert result == {"laws": 1, "cases": 6, "blocked_branches": []}, result
    print(json.dumps({"validator": "worker_exchange.branch_coverage.validate", "result": result,
                      "proposal_sha256": sha(HERE / "proposals" / "branch-coverage-proposal.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
