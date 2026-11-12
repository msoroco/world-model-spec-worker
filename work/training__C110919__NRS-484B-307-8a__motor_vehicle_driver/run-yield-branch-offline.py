"""Run all eight draft yield constructions through pinned offline materialization."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-yield-branch-execution-manifest.json"
OUTPUT = ROOT / ".runtime-work/c110919-update034-yield-offline"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest["cases"]:
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            destination = OUTPUT / suffix / candidate
            completed = subprocess.run([sys.executable, str(ROOT / "runtime.py"),
                                        "offline", "--manifest", str(MANIFEST),
                                        "--case", case["case_id"], "--candidate", candidate,
                                        "--output", str(destination), "--python", sys.executable],
                                       capture_output=True, text=True, check=True)
            result = json.loads(completed.stdout)
            if not (result["offline_passed"] is True and
                    result["simulation_started"] is False and
                    result["case_id"] == case["case_id"] and
                    result["candidate_id"] == candidate):
                raise ValueError("Exact offline result differs")
            construction = (case["construction"] if candidate == "primary" else
                            next(row["construction"] for row in case["candidates"]
                                 if row["id"] == candidate))
            rows.append({"case_id": case["case_id"], "candidate_id": candidate,
                         "construction_sha256": sha(HERE / construction),
                         "offline_log_sha256": sha(Path(result["log"])),
                         "offline_passed": True, "simulation_started": False})
    proof = {"format": "c110919-yield-branch-offline-matrix-v1",
             "manifest_sha256": sha(MANIFEST), "rows": rows,
             "canonical_selected": False, "physical_acceptance_claimed": False}
    target = HERE / "yield_branch_cases/yield-offline-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"bundles": len(rows), "proof_sha256": sha(target),
                      "canonical_selected": False}))


if __name__ == "__main__":
    main()
