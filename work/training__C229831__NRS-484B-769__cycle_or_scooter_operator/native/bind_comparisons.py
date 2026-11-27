"""Run exact controlled comparisons and bind independent source audits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
SCRIPT = FOLDER / "comparison_audit.py"
PLAN = FOLDER / "case-plan.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for item in plan["comparisons"]:
        first, second = item["case_ids"]
        label_a, label_b = (case.rsplit("_", 1)[-1] for case in (first, second))
        root_a = SCRATCH / f"compat-{label_a}-primary-v2"
        root_b = SCRATCH / f"compat-{label_b}-primary-v2"
        label = "general_vs_exception" if item["comparison_id"].endswith(
            "__general_vs_exception") else "signal_vs_none"
        target = FOLDER / "proofs/comparisons"
        target.mkdir(parents=True, exist_ok=True)
        output = target / (label + ".json")
        log = target / (label + ".log")
        command = [sys.executable, str(SCRIPT), "--root-a", str(root_a),
                   "--root-b", str(root_b), "--case-a", first,
                   "--case-b", second, "--comparison", item["comparison_id"],
                   "--output", str(output)]
        run = subprocess.run(command, env=env, capture_output=True, text=True)
        log.write_text((run.stdout + run.stderr).strip() + "\n")
        if run.returncode:
            raise ValueError("Comparison audit failed: " + log.read_text()[-500:])
        audit = json.loads(output.read_text())
        if audit["comparison_id"] != item["comparison_id"] or not audit["diagnostic_fixture"]:
            raise ValueError("Comparison audit differs")
        item["audit"] = {"command": " ".join(command), "exit_code": run.returncode,
                         "script": SCRIPT.relative_to(FOLDER).as_posix(),
                         "script_sha256": sha(SCRIPT),
                         "report": output.relative_to(FOLDER).as_posix(),
                         "report_sha256": sha(output),
                         "log": log.relative_to(FOLDER).as_posix(),
                         "log_sha256": sha(log),
                         "scope": "synthetic diagnostic source contrast; original pixels and legal review pending"}
    PLAN.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"independent_comparisons": len(plan["comparisons"]),
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
