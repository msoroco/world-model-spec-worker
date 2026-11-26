"""Bind diagnostic pair comparisons and original-source rejection."""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    data = json.loads(MANIFEST.read_text())
    case_by_id = {entry["case_id"]: entry for entry in data["cases"]}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c135087-runtime-output"))
    data["comparisons"] = json.loads((ROOT / "case-plan.json").read_text())["comparisons"]
    for comparison in data["comparisons"]:
        left_case, right_case = comparison["case_ids"]
        suffixes = [case.removeprefix(ROOT.name + "__") for case in (left_case, right_case)]
        attempts = [REPO / ".runtime-work/c135087-saved-v6" / ("saved-" + suffix) / "v0001/analysis"
                    for suffix in suffixes]
        base = [PYTHON, str(ROOT / "selected_comparison.py"), "--left", str(attempts[0]),
                "--right", str(attempts[1]), "--left-case", left_case,
                "--right-case", right_case]
        positive = subprocess.run(base + ["--allow-diagnostic"], cwd=REPO, env=env,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        positive_log = ROOT / ("cpu-comparison-" + comparison["comparison_id"] + ".log")
        positive_log.write_text(positive.stdout.rstrip() + "\n")
        if positive.returncode:
            raise ValueError("diagnostic comparison failed: " + positive.stdout[-1000:])
        negative = subprocess.run(base, cwd=REPO, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        negative_log = ROOT / ("cpu-comparison-negative-" + comparison["comparison_id"] + ".log")
        negative_log.write_text(negative.stdout.rstrip() + "\n")
        expected = "independent original comparison source hashes required"
        if negative.returncode == 0 or expected not in negative.stdout:
            raise ValueError("original comparison missing-source rejection failed")
        comparison["comparison_audit"] = {
            "script": "selected_comparison.py", "script_sha256": sha(ROOT / "selected_comparison.py"),
            "case_ids": [left_case, right_case], "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "test_command": " ".join(base + ["--allow-diagnostic"]), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(base), "negative_exit_code": negative.returncode,
            "negative_expected_error": expected, "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "source_case_hashes": [case_by_id[case]["saved_diagnostic"]["sha256"]
                                   for case in (left_case, right_case)]}
        print(comparison["comparison_id"] + " comparison proof passed", flush=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
