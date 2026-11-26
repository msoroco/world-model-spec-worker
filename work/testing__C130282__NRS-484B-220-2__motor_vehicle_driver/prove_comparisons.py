"""Prove the three planned exact comparisons on source-bound CPU diagnostics."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c130282/comparisons"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if REPO / ".runtime-work" not in Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().parents:
        raise ValueError("output root must be under .runtime-work")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = []
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    for item in plan["comparisons"]:
        cid = item["comparison_id"]
        output = SCRATCH / (cid + ".json")
        output.unlink(missing_ok=True)
        command = [sys.executable, str(ROOT / "comparison_audit.py"),
                   "--comparison-id", cid, "--plan", str(ROOT / "case-plan.json")]
        for case_id in item["case_ids"]:
            command.extend(("--attempt", str(REPO / ".runtime-work/c130282/selected" /
                case_id.split("__")[-1] / "primary/compatibility")))
        command.extend(("--output", str(output), "--diagnostic"))
        run = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
        log = ROOT / ("proof-comparison-" + cid + ".log")
        log.write_text((run.stdout + run.stderr).rstrip() + "\n", encoding="utf-8")
        if run.returncode:
            raise RuntimeError(cid + ": " + log.read_text()[-1500:])
        proof = json.loads(output.read_text(encoding="utf-8"))
        if proof["case_ids"] != item["case_ids"] or not proof["fixed_context_checked"] or not proof["deliberate_difference_checked"]:
            raise ValueError("comparison source isolation incomplete")
        results.append({"comparison_id": cid, "case_ids": item["case_ids"],
            "command": " ".join(command), "exit_code": 0,
            "log": log.name, "log_sha256": sha(log),
            "audit_sha256": sha(output), "diagnostic_fixture": True})
        print(cid, "passed", flush=True)
    (ROOT / "comparison-proof-index.json").write_text(json.dumps({"assignment_id": ROOT.name,
        "comparisons": results}, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
