"""Run positive and source-missing independent-auditor CPU self tests."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
AUDITOR = ROOT / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    temp = SCRATCH / (path.name + ".staging")
    temp.write_text(content.rstrip() + "\n")
    os.replace(temp, path)


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        base = [sys.executable, "-B", str(AUDITOR), "--case", case_id, "--self-test"]
        positive = subprocess.run(base, cwd=REPO, text=True, capture_output=True, timeout=30)
        negative = subprocess.run(base + ["--negative"], cwd=REPO,
                                  text=True, capture_output=True, timeout=30)
        expected = "Original marked-lane and immediately-following traffic source unverified"
        if (positive.returncode != 0 or negative.returncode == 0 or
                expected not in negative.stderr):
            raise ValueError("Independent source audit CPU test failed: " + suffix)
        log = ROOT / "delivery-audit" / (suffix + "-positive.log")
        negative_log = ROOT / "delivery-audit" / (suffix + "-negative.log")
        atomic(log, positive.stdout)
        atomic(negative_log, negative.stderr)
        rows.append({"case_id": case_id, "script": "delivery_audit.py",
                     "script_sha256": sha(AUDITOR),
                     "command": " ".join(base), "test_exit_code": 0,
                     "test_log": str(log.relative_to(ROOT)), "test_log_sha256": sha(log),
                     "negative_command": " ".join(base + ["--negative"]),
                     "negative_exit_code": negative.returncode,
                     "negative_expected_error": expected,
                     "negative_log": str(negative_log.relative_to(ROOT)),
                     "negative_log_sha256": sha(negative_log)})
        print(json.dumps({"case": suffix, "positive": 0,
                          "negative": negative.returncode}), flush=True)
    atomic(ROOT / "delivery-audit/index.json",
           json.dumps({"format": "worker-c132924-delivery-audit-cpu-proof-v1",
                       "cases": rows, "passed": len(rows),
                       "scope": "auditor predicate self tests, no original capture attested"}, indent=2))


if __name__ == "__main__":
    main()
