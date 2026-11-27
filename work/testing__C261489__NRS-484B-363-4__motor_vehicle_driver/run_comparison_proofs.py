"""Run nine exact controlled comparison audits on case-specific CPU fixtures."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c261489-owner-nov27b"
ASSIGNMENT = HERE.name
SCRIPT = HERE / "comparison_audit.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE="1")
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        left, right = comparison["case_ids"]
        lname, rname = left[len(ASSIGNMENT) + 2:], right[len(ASSIGNMENT) + 2:]
        la = SCRATCH / ("compat-" + lname + "-v3")
        ra = SCRATCH / ("compat-" + rname + "-v3")
        result = SCRATCH / ("comparison-" + cid + ".json")
        command = [str(REPO / ".venv-cpu/bin/python"), str(SCRIPT), "--comparison", cid,
                   "--left-case", left, "--left-attempt", str(la),
                   "--right-case", right, "--right-attempt", str(ra), "--output", str(result)]
        process = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 capture_output=True, timeout=90)
        if process.returncode:
            raise ValueError(cid + " comparison failed: " + process.stderr[-1800:])
        audited = json.loads(result.read_text())
        if audited.get("comparison_id") != cid or audited.get("case_ids") != [left, right]:
            raise ValueError("comparison result changed: " + cid)
        log = HERE / ("cpu-comparison-" + cid + ".log")
        log.write_text("diagnostic comparison audit passed: " + cid + "\n")
        rows.append({"comparison_id": cid, "case_ids": [left, right],
                     "command": shlex.join(command), "script": SCRIPT.name,
                     "script_sha256": sha(SCRIPT), "test_exit_code": 0,
                     "test_log": log.name, "test_log_sha256": sha(log),
                     "diagnostic_only": True})
        print(cid, "comparison audit passed", flush=True)
    (HERE / "comparison-proofs.json").write_text(json.dumps({
        "format": "worker-comparison-proof-proposal", "assignment_id": ASSIGNMENT,
        "comparisons": rows,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
