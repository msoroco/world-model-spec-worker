"""Check this assignment's selected queue intent and synthetic integration proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SHARED = ROOT / "work/_shared"
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    queue_path = SHARED / "gpu-queue.json"
    queue = json.loads(queue_path.read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    proof = json.loads((SHARED / "local-integration-proof.json").read_text())
    rows = [row for row in queue["cases"] if row["assignment_id"] == AID]
    comps = [row for row in queue["comparison_audit_commands"] if row["assignment_id"] == AID]
    cases = {case["case_id"] for case in manifest["cases"]}
    expected_cases = {case["case_id"] for case in plan["cases"]}
    expected_comps = {item["comparison_id"] for item in plan["comparisons"]}
    assert len(cases) == len(rows) == len(expected_cases) == 8
    assert {row["case_id"] for row in rows} == cases == expected_cases
    assert len(comps) == len(expected_comps) == 3
    assert {row["comparison_id"] for row in comps} == expected_comps
    assert result["status"] == "partial" and result["cases_selected"] == 8
    assert all(row["selected"] is True and row["dispatchable"] is False and
               row["status"] == "partial" for row in rows + comps)
    assert [row["order"] for row in queue["cases"]] == list(range(1, len(queue["cases"]) + 1))
    for row in rows:
        cid = row["case_id"]
        for key in ("prepare_command", "execute_command", "capture_command",
                    "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command", "accept_command"):
            assert cid in row[key], (cid, key)
        assert "--review-archive ${REVIEW_ARCHIVE}" in row["accept_command"]
        assert "--assignment " + AID in row["additional_source_audit_command"]
        for candidate in ("fallback1", "fallback2", "fallback3"):
            assert cid in row["candidate_commands"][candidate]
            assert candidate in row["candidate_commands"][candidate]
    assert proof["passed"] is True and proof["synthetic_only"] is True
    assert proof["original_native_executed"] is False
    assert proof["physical_validation_mocked"] is True
    assert proof["accepted_recordings_claimed"] is False
    assert sha(ROOT / proof["log"]) == proof["log_sha256"]
    assert sha(SHARED / "prove-local-delivery-diagnostic.py") == proof["harness_sha256"]
    receipt = {"format": "assignment-queue-integration-audit", "passed": True,
               "assignment_id": AID, "queue_sha256": sha(queue_path),
               "integration_proof_sha256": sha(SHARED / "local-integration-proof.json"),
               "selected_cases": len(rows), "selected_comparisons": len(comps),
               "synthetic_only": True, "canonical_delivery_accepted": False}
    (HERE / "final-queue-integration-audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
