"""Independent CPU closure for the two C329610 signaling distance branches."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
AID = HERE.name
LAW = "NRS-484B-413-2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    matrix = json.loads((REPO / "work/_shared/branch-coverage.json").read_text())
    frozen = json.loads((REPO / "inputs/coverage/branch-sources.json").read_text())["laws"][LAW]
    branches = [row for row in matrix["laws"][LAW]["branches"] if row.get("assignment_id") == AID]
    assert len(branches) == 2
    assert {row["branch_id"].split("__")[0] for row in branches} == {
        "continuous_signal_100_ft", "continuous_signal_300_ft"}
    assert set().union(*(set(row["topic_ids"]) for row in branches)) == set(frozen["topics"])
    assert {row["status"] for row in branches} <= {"pending_review", "runnable"}
    cases = {row["case_id"]: row for row in plan["cases"]}
    comparisons = {row["comparison_id"]: row for row in plan["comparisons"]}
    assert len(cases) == 6 and len(comparisons) == 2
    for branch in branches:
        ids = set(branch["case_ids"])
        assert len(ids) == 3 and ids <= set(cases)
        assert len(branch["comparison_ids"]) == 1
        comparison = comparisons[branch["comparison_ids"][0]]
        assert ids == set(comparison["case_ids"])
        settings = sorted(cases[ident]["requested_setting"] for ident in ids)
        assert settings in ([90, 100, 110], [290, 300, 310])
        assert len({cases[ident]["area_classification"] for ident in ids}) == 1
    result = json.loads((HERE / "result.json").read_text())
    assert result["status"] == "blocked" and result["cases_selected"] == 0
    checks = ["audit-draft-offline.py", "audit-package-probes.py", "audit-signal-fixtures.py",
              "audit-saved-package.py", "audit-case-trigger-coverage.py"]
    for script in checks:
        completed = subprocess.run([sys.executable, str(HERE / script)], cwd=REPO,
                                   capture_output=True, text=True, timeout=90)
        if completed.returncode:
            raise AssertionError(script + ": " + completed.stdout + completed.stderr)
    coverage = json.loads((HERE / "case-trigger-coverage.json").read_text())
    assert len(coverage["cases"]) == 6 and coverage["selected"] is False
    proof = {name: sha(HERE / name) for name in (
        "draft-execution-manifest.json", "draft-offline-summary.json",
        "draft-package-probe-summary.json", "saved-package-summary.json",
        "signal-fixture-summary.json", "case-trigger-coverage.json",
        "case-trigger-coverage-audit.log")}
    print(json.dumps({"passed": True, "law_id": LAW, "branches": 2,
                      "cases": 6, "controlled_comparisons": 2,
                      "exact_offline_bundles": 24, "synthetic_v1_pairs": 24,
                      "source_hashed_trigger_cases": 6, "proof_sha256": proof,
                      "selected": False, "original_native_observed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
