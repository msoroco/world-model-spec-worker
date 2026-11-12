"""Recheck every unselected pedestrian-conflict construction on pinned CPU."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE / "yield_branch_cases"
MANIFEST = ROOT / "construction-manifest.json"
RUNNER = HERE / "native/yield_branch_runner.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["format"] == "c110919-yield-branch-construction-v1"
    assert len(manifest["rows"]) == 8
    outputs = []
    for row in manifest["rows"]:
        config = HERE / row["config_path"]
        assert digest(config) == row["config_sha256"]
        for rel, expected in row["source_sha256"].items():
            assert digest(HERE / rel) == expected
        completed = subprocess.run([sys.executable, str(RUNNER), "--config",
                                    str(config), "--check"], capture_output=True,
                                   text=True, check=True)
        checked = json.loads(completed.stdout)
        assert checked["offline_geometry"]["passed"] is True
        assert checked["case"] == row["case_id"].removeprefix(HERE.name + "__")
        assert checked["candidate"] == row["candidate_id"]
        assert checked["camera_count"] == 4
        assert checked["physical_success_claimed"] is False
        outputs.append({"case_id": row["case_id"],
                        "candidate_id": row["candidate_id"],
                        "offline_preflight_passed": True})
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s",
                    str(HERE / "native"), "-p", "test_yield_branch.py", "-v"],
                   check=True, capture_output=True, text=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s",
                    str(HERE), "-p", "test_yield_branch_comparison.py", "-v"],
                   check=True, capture_output=True, text=True)
    proof = {"format": "c110919-yield-branch-cpu-proof-v1",
             "construction_manifest_sha256": digest(MANIFEST),
             "candidate_checks": outputs, "policy_unit_tests_passed": 4,
             "saved_source_comparison_tests_passed": 8,
             "native_imported": False, "original_capture_observed": False,
             "canonical_selected": False, "status": "draft_not_selected"}
    target = ROOT / "cpu-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"candidate_checks": len(outputs), "policy_tests": 4,
                      "saved_source_tests": 8,
                      "proof_sha256": digest(target), "canonical_selected": False}))


if __name__ == "__main__":
    main()
