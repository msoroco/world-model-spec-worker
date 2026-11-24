"""Run public pinned offline checks for the primary and two reviewed fallbacks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name
SCRATCH = ROOT / ".runtime-work/c104496-reviewed-offline-media-v4"
CASES = (("crest", "probe_01"), ("crest", "probe_02"), ("curve", "probe_03"))
CHOICES = ("primary", "fallback1", "fallback2")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    review = json.loads((HERE / "candidate-risk-review.json").read_text())
    if review["status"] != "draft_review_only" or review["rejected_mutations"] != 15:
        raise ValueError("Candidate review absent or stale")
    if len(review["case_reviews"]) != 3 or any(
            row["selected_candidate_ids"] != ["fallback1", "fallback2"]
            for row in review["case_reviews"]):
        raise ValueError("Candidate policy differs")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    rows = []
    for branch, case in CASES:
        manifest = HERE / branch / "draft-execution-manifest.json"
        case_id = ASSIGNMENT + "__" + case
        for choice in CHOICES:
            output = SCRATCH / branch / case / choice / "materialized"
            output.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest",
                   str(manifest), "--case", case_id, "--output", str(output),
                   "--python", sys.executable]
            if choice != "primary":
                cmd += ["--candidate", choice]
            env = dict(os.environ, TMPDIR=str(SCRATCH),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                       PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                 text=True, timeout=300)
            if run.returncode:
                raise RuntimeError(f"{branch}/{case}/{choice}: {run.stderr[-1200:]}")
            rows.append({"case_id": case_id, "candidate": choice,
                         "manifest_sha256": sha(manifest), "exit_code": 0,
                         "stdout_sha256": hashlib.sha256(run.stdout.encode()).hexdigest(),
                         "stderr_sha256": hashlib.sha256(run.stderr.encode()).hexdigest()})
    proof = {"format": "c104496-reviewed-draft-offline-v1",
             "assignment_id": ASSIGNMENT,
             "candidate_review_sha256": sha(HERE / "candidate-risk-review.json"),
             "runtime_py_sha256": sha(ROOT / "runtime.py"), "results": rows,
             "passed": len(rows) == 9, "selected_delivery_cases": 0,
             "source_media_or_physical_proven": False}
    (HERE / "reviewed-offline-proof.json").write_text(
        json.dumps(proof, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"passed": proof["passed"], "checks": len(rows),
                      "proof_sha256": sha(HERE / "reviewed-offline-proof.json")}))


if __name__ == "__main__":
    main()
