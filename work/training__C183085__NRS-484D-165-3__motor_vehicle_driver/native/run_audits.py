"""Run independent saved-source and comparison diagnostic audits."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / "native"
SCRATCH = REPO / ".runtime-work/c183085-audits-v6"
SCRATCH.mkdir(exist_ok=True)
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, log):
    result = subprocess.run(command, cwd=REPO, env=ENV, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    manifest_path = ROOT / "selected-proof-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    delivery_script = ROOT / "delivery_audit.py"
    proofs = {}
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.split("__")[-1]
        version = "v7" if suffix.startswith(("numeric_2_", "numeric_3_")) else "v6"
        attempt = REPO / (".runtime-work/c183085-compat-" + version + "-" + suffix)
        processing = NATIVE / ("selected-" + suffix + "-saved-processing.json")
        output = SCRATCH / (suffix + "-delivery.json")
        command = [".venv-cpu/bin/python", str(delivery_script.relative_to(REPO)),
                   "--case", case, "--candidate", "primary", "--attempt",
                   str(attempt.relative_to(REPO)), "--processing",
                   str(processing.relative_to(REPO)), "--output",
                   str(output.relative_to(REPO)), "--diagnostic"]
        positive_log = NATIVE / ("selected-" + suffix + "-delivery-positive.log")
        negative_log = NATIVE / ("selected-" + suffix + "-delivery-negative.log")
        positive = execute(command, positive_log)
        negative_command = command + ["--omit-source", "optical_measurements.json"]
        negative = execute(negative_command, negative_log)
        if positive != 0 or negative == 0 or \
                "Missing source: optical_measurements.json" not in negative_log.read_text():
            raise ValueError("Delivery audit failed: " + suffix + " " + str((positive, negative)))
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion",
                       "independent_optical_review"],
            "script": "delivery_audit.py", "script_sha256": sha(delivery_script),
            "command": " ".join(command), "test_exit_code": 0,
            "test_log": str(positive_log.relative_to(ROOT)),
            "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative_command),
            "negative_exit_code": negative,
            "negative_expected_error": "Missing source: optical_measurements.json",
            "negative_log": str(negative_log.relative_to(ROOT)),
            "negative_log_sha256": sha(negative_log),
        }
        proofs[case] = (processing, output)
        print("delivery", suffix, flush=True)
    comparison_script = ROOT / "comparison_audit.py"
    for comparison in plan["comparisons"]:
        comparison_id = comparison["comparison_id"]
        name = comparison_id.split("__")[-1]
        command = [".venv-cpu/bin/python", str(comparison_script.relative_to(REPO)),
                   "--comparison-id", comparison_id]
        for label, case in zip("abc", comparison["case_ids"]):
            processing, audit = proofs[case]
            command += ["--" + label + "-processing", str(processing.relative_to(REPO)),
                        "--" + label + "-audit", str(audit.relative_to(REPO))]
        command += ["--output", str((SCRATCH / (name + "-comparison.json")).relative_to(REPO)),
                    "--diagnostic"]
        positive_log = NATIVE / (name + "-comparison-positive.log")
        negative_log = NATIVE / (name + "-comparison-negative.log")
        positive = execute(command, positive_log)
        negative_command = command + ["--omit-b-audit"]
        negative = execute(negative_command, negative_log)
        if positive != 0 or negative == 0 or \
                "Missing independent B audit" not in negative_log.read_text():
            raise ValueError("Comparison audit failed: " + name + " " + str((positive, negative)))
        record = {"script": "comparison_audit.py", "script_sha256": sha(comparison_script),
                  "positive_log": str(positive_log.relative_to(ROOT)),
                  "positive_log_sha256": sha(positive_log),
                  "negative_log": str(negative_log.relative_to(ROOT)),
                  "negative_log_sha256": sha(negative_log)}
        for entry in manifest["cases"]:
            if entry["case_id"] in comparison["case_ids"]:
                entry["comparison_audit"] = record
        print("comparison", name, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(proofs), "comparisons": len(plan["comparisons"]),
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
