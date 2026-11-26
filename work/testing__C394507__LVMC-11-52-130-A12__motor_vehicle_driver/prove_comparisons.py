"""Run eight exact diagnostic fixed-context pair audits."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c394507-nov26"
PYTHON = str(REPO / ".venv-cpu/bin/python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    os.environ["TMPDIR"] = os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    attempts = {}
    for entry in manifest["cases"]:
        tokens = shlex.split(entry["compatibility"]["command"])
        attempts[entry["case_id"]] = tokens[tokens.index("--output") + 1]
    results = []
    for row in plan["comparisons"]:
        command = [PYTHON, str(HERE / "comparison_audit.py")]
        for case_id in row["case_ids"]:
            command.extend(("--attempt", attempts[case_id]))
        output = SCRATCH / ("comparison-" + row["comparison_id"] + "-" +
                            str(time.time_ns()) + ".json")
        command.extend(("--comparison-id", row["comparison_id"],
                        "--plan", str(HERE / "case-plan.json"),
                        "--output", str(output)))
        process = subprocess.run(command, cwd=REPO, env=os.environ,
                                 capture_output=True, text=True, timeout=300)
        log = HERE / ("proof-comparison-" + row["comparison_id"] + ".log")
        body = (process.stdout + process.stderr).rstrip()
        log.write_text(body + "\n" if body else "")
        if process.returncode:
            raise RuntimeError(row["comparison_id"] + ": " + log.read_text()[-1800:])
        proof = json.loads(output.read_text())
        if (proof.get("case_ids") != row["case_ids"] or
                proof.get("fixed_context_checked") is not True or
                proof.get("deliberate_difference_checked") is not True):
            raise ValueError("comparison independent check incomplete")
        results.append({"comparison_id": row["comparison_id"],
                        "case_ids": row["case_ids"],
                        "command": " ".join(command), "exit_code": 0,
                        "log": log.name, "log_sha256": sha(log),
                        "audit_sha256": sha(output), "diagnostic_fixture": True})
        print(row["comparison_id"], "passed", flush=True)
    (HERE / "comparison-proof-index.json").write_text(
        json.dumps({"assignment_id": HERE.name, "comparisons": results},
                   sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
