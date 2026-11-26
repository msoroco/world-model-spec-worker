"""Run all five exact diagnostic comparisons without claiming original review."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c255863-new/comparisons"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_of(command: str) -> Path:
    tokens = shlex.split(command)
    return Path(tokens[tokens.index("--output") + 1])


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    attempts = {entry["case_id"]: output_of(entry["compatibility"]["command"])
                for entry in manifest["cases"]}
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proofs = []
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        left, right = comparison["case_ids"]
        command = [sys.executable, str(ROOT / "diagnostic_comparison_audit.py"),
                   "--comparison", cid, "--left", str(attempts[left]),
                   "--right", str(attempts[right]), "--output", str(SCRATCH / (cid + ".json"))]
        output = Path(command[-1])
        output.unlink(missing_ok=True)
        run = subprocess.run(command, cwd=REPO, env=os.environ, text=True, capture_output=True)
        log = ROOT / ("cpu-comparison-" + cid + ".log")
        message = (run.stdout + run.stderr).rstrip() or (
            "diagnostic comparison audit exited " + str(run.returncode))
        log.write_text(message + "\n", encoding="utf-8")
        if run.returncode:
            raise RuntimeError(cid + ": " + log.read_text()[-2000:])
        result = json.loads(output.read_text())
        if (result["case_ids"] != comparison["case_ids"] or
                not result["fixed_diagnostic_context_and_camera_protocol_checked"] or
                not result["deliberate_difference_checked"] or
                result["diagnostic_fixture"] is not True):
            raise ValueError("diagnostic comparison isolation incomplete")
        proofs.append({"comparison_id": cid, "case_ids": comparison["case_ids"],
                       "command": shlex.join(command), "exit_code": 0,
                       "log": log.name, "log_sha256": sha(log),
                       "audit_sha256": sha(output), "diagnostic_fixture": True})
        print(cid, "diagnostic comparison passed", flush=True)
    (ROOT / "comparison-proof-index.json").write_text(
        json.dumps({"assignment_id": ROOT.name, "comparisons": proofs},
                   sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
