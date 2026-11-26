"""Run exact-case independent positive and missing-source delivery audits."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SCRIPT = HERE / "delivery-audit.py"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = REPO / ".runtime-work" / "c247014-resume-v5"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        attempt = REPO / ".runtime-work" / ("c247014-compat-" + suffix + "-v4")
        folder = HERE / "proofs" / "delivery" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        positive = folder / "positive.json"
        command = [sys.executable, "-B", str(SCRIPT), "--attempt", str(attempt),
                   "--case", case, "--output", str(positive), "--diagnostic"]
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=180)
        if run.returncode or run.stderr:
            raise ValueError("Independent delivery positive failed: " + suffix + " " + run.stderr)
        result = json.loads(positive.read_text())
        if (result["case_id"] != case or result["frames"] != 600 or
                result["physical_acceptance"] or result["original_native_observed"] or
                not set(CHECKS) <= set(result["checks"])):
            raise ValueError("Delivery audit made an unsupported claim")
        positive_log = folder / "positive.log"
        positive_log.write_text(run.stdout)
        negative = [sys.executable, "-B", str(SCRIPT), "--attempt", str(attempt),
                    "--case", case, "--output", str(scratch / ("delivery-negative-" + suffix + ".json")),
                    "--diagnostic", "--omit", "pass-context.json"]
        run = subprocess.run(negative, cwd=REPO, capture_output=True, text=True, timeout=180)
        negative_log = folder / "negative.log"
        negative_log.write_text(run.stdout + run.stderr)
        if run.returncode == 0 or "Missing delivery source: pass-context.json" not in negative_log.read_text():
            raise ValueError("Independent missing-source negative did not reject")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": CHECKS,
            "command": " ".join(command), "test_exit_code": 0,
            "negative_command": " ".join(negative), "negative_exit_code": run.returncode,
            "negative_expected_error": "Missing delivery source: pass-context.json",
            "script": str(SCRIPT.relative_to(HERE)), "script_sha256": sha(SCRIPT),
            "test_log": str(positive_log.relative_to(HERE)), "test_log_sha256": sha(positive_log),
            "negative_log": str(negative_log.relative_to(HERE)), "negative_log_sha256": sha(negative_log),
            "positive_result": str(positive.relative_to(HERE)), "positive_result_sha256": sha(positive),
        }
    write(MANIFEST, manifest)
    print(json.dumps({"bound": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST)}, sort_keys=True))


if __name__ == "__main__":
    main()
