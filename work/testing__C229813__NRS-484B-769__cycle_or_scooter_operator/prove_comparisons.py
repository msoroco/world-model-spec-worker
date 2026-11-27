"""Run positive and source-swap negative comparison CPU fixtures."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
SCRATCH = REPO / ".runtime-work/c229813-owner/compat-all-v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = PACKAGE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for row in plan["comparisons"]:
        comparison_id = row["comparison_id"]
        attempts = [str(SCRATCH / (case_id.removeprefix(PACKAGE.name + "__") + "-primary"))
                    for case_id in row["case_ids"]]
        base = [sys.executable, str(PACKAGE / "compare_saved.py"),
                "--comparison", comparison_id, "--diagnostic"]
        positive_command = base + [part for attempt in attempts for part in ("--attempt", attempt)]
        negative_attempts = [attempts[0], attempts[0], attempts[2]]
        negative_command = base + [part for attempt in negative_attempts for part in ("--attempt", attempt)]
        results = []
        for kind, command in (("positive", positive_command), ("negative", negative_command)):
            run = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            log = PACKAGE / f"proof-comparison-{comparison_id}-{kind}.log"
            log.write_text((run.stdout + run.stderr).rstrip() + "\n")
            results.append((run.returncode, log, " ".join(command)))
        positive, negative = results
        expected = "comparison source case mismatch"
        if positive[0] != 0 or negative[0] == 0 or expected not in negative[1].read_text():
            raise ValueError("comparison CPU proof failed: " + comparison_id)
        row["audit"] = {"script": "compare_saved.py", "script_sha256": sha(PACKAGE / "compare_saved.py"),
                        "command": positive[2], "test_exit_code": 0,
                        "test_log": positive[1].name, "test_log_sha256": sha(positive[1]),
                        "negative_command": negative[2], "negative_exit_code": negative[0],
                        "negative_expected_error": expected,
                        "negative_log": negative[1].name,
                        "negative_log_sha256": sha(negative[1]),
                        "scope": "Diagnostic CPU comparison checker; original source comparison pending"}
        print(comparison_id, "PASS", flush=True)
    plan_path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
