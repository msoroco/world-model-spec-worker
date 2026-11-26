"""CPU self tests of exact original-source comparison rejection predicates."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
SCRIPT = ROOT / "comparison_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + ".comparison-stage")
    stage.write_text(content.rstrip() + "\n")
    os.replace(stage, path)


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        suffix = ident.rsplit("__", 1)[-1]
        command = [sys.executable, "-B", str(SCRIPT), "--comparison", ident, "--self-test"]
        positive = subprocess.run(command, capture_output=True, text=True, timeout=30)
        negative_command = command + ["--negative"]
        negative = subprocess.run(negative_command, capture_output=True, text=True, timeout=30)
        if positive.returncode != 0 or negative.returncode == 0 or "Undeclared comparison source difference" not in negative.stderr:
            raise AssertionError("Comparison predicate selftest failed: " + suffix + " " + positive.stderr[-500:] + negative.stderr[-500:])
        directory = ROOT / "comparison-audit"
        pos_log = directory / (suffix + "-positive.log")
        neg_log = directory / (suffix + "-negative.log")
        atomic(pos_log, positive.stdout)
        atomic(neg_log, negative.stderr)
        rows.append({"comparison_id": ident, "case_ids": comparison["case_ids"],
                     "script": "comparison_audit.py", "script_sha256": sha(SCRIPT),
                     "positive_command": " ".join(command), "positive_exit_code": 0,
                     "positive_log": str(pos_log.relative_to(ROOT)),
                     "positive_log_sha256": sha(pos_log),
                     "negative_command": " ".join(negative_command),
                     "negative_exit_code": negative.returncode,
                     "negative_expected_error": "Undeclared comparison source difference",
                     "negative_log": str(neg_log.relative_to(ROOT)),
                     "negative_log_sha256": sha(neg_log),
                     "original_capture_attested": False})
    index = ROOT / "comparison-audit/index.json"
    atomic(index, json.dumps({"format": "worker-nrs280-comparison-audit-tests-v1",
                              "comparisons": rows}, indent=2))
    print(json.dumps({"comparison_selftests": len(rows),
                      "index_sha256": sha(index)}))


if __name__ == "__main__":
    main()
