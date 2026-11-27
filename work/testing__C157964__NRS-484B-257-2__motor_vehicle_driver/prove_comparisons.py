"""Bind five exact observed comparisons and report-tamper rejections."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c157964-nov27"
SCRIPT = ROOT / "comparison_audit.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    p = subprocess.run(command, cwd=REPO, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(p.stdout.rstrip("\n") + "\n")
    return p.returncode


def main():
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    proofs = []
    for row in plan["comparisons"]:
        cid = row["comparison_id"]
        a, b = [case.removeprefix(ROOT.name + "__") for case in row["case_ids"]]
        left = SCRATCH / ("saved-proof-" + a + "-v3/v0001/analysis")
        right = SCRATCH / ("saved-proof-" + b + "-v3/v0001/analysis")
        output = ROOT / ("observed-comparison-" + cid + ".json")
        if output.exists():
            output.unlink()
        command = [sys.executable, str(SCRIPT), "--comparison", cid, "--left", str(left),
                   "--right", str(right), "--diagnostic-fixture", "--output", str(output)]
        positive = ROOT / ("cpu-comparison-" + cid + "-positive.log")
        if run(command, positive) or not output.is_file():
            raise ValueError("comparison positive failed: " + positive.read_text()[-1300:])
        corrupted = SCRATCH / ("comparison-corrupt-" + cid + "-v1")
        if corrupted.exists():
            shutil.rmtree(corrupted)
        shutil.copytree(left, corrupted)
        report_path = corrupted / "analysis-report.json"
        report = json.loads(report_path.read_text())
        report["measurements"]["officer_intersection_motion"]["value"]["motion"][
            "observed_officer_directive_at_entry"] = "unobserved"
        report_path.write_text(json.dumps(report, sort_keys=True) + "\n")
        negative_output = SCRATCH / ("comparison-rejected-" + cid + "-v1.json")
        if negative_output.exists():
            negative_output.unlink()
        negative_command = [sys.executable, str(SCRIPT), "--comparison", cid,
                            "--left", str(corrupted), "--right", str(right),
                            "--diagnostic-fixture", "--output", str(negative_output)]
        negative = ROOT / ("cpu-comparison-" + cid + "-negative.log")
        code = run(negative_command, negative)
        error = "saved source measurement differs"
        if code == 0 or error not in negative.read_text() or negative_output.exists():
            raise ValueError("comparison report-tamper rejection failed")
        proofs.append({"comparison_id": cid, "case_ids": row["case_ids"],
                       "audit": output.name, "audit_sha256": sha(output),
                       "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
                       "command": " ".join(command), "exit_code": 0,
                       "log": positive.name, "log_sha256": sha(positive),
                       "negative_command": " ".join(negative_command),
                       "negative_exit_code": code, "negative_expected_error": error,
                       "negative_log": negative.name, "negative_log_sha256": sha(negative),
                       "physical_acceptance_claimed": False})
        print("observed comparison passed", cid, flush=True)
    proof_path = ROOT / "comparison-proofs.json"
    proof_path.write_text(json.dumps({"format": "c157964-comparison-proofs-v1",
                                      "comparisons": proofs}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
