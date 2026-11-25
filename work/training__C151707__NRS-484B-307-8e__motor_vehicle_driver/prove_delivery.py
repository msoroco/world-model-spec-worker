"""Run diagnostic acceptance and Native-source rejection for both exact cases."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / "delivery_audit.py"
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


m = json.loads(MANIFEST.read_text())
for entry in m["cases"]:
    suffix = entry["case_id"].rsplit("__", 1)[-1]
    number = suffix[-2:]
    area = ROOT / "proofs" / suffix / "delivery"
    area.mkdir(parents=True, exist_ok=True)
    attempt = REPO / ".runtime-work" / ("c151707-public-road-v1" if number == "01" else "c151707-public-property-v2")
    processing = REPO / ".runtime-work" / ("c151707-saved-road-v1" if number == "01" else "c151707-saved-property-v1") / "v0001/processing.json"
    base = [sys.executable, str(SCRIPT), "--case", entry["case_id"], "--candidate", "primary",
            "--attempt", str(attempt), "--processing", str(processing), "--output", str(area / "diagnostic.json")]
    positive = subprocess.run([*base, "--diagnostic"], capture_output=True, text=True)
    negative = subprocess.run(base, capture_output=True, text=True)
    (area / "positive.log").write_text((positive.stdout + positive.stderr).rstrip("\n") + "\n")
    (area / "negative.log").write_text((negative.stdout + negative.stderr).rstrip("\n") + "\n")
    if positive.returncode != 0 or negative.returncode == 0 or "Original Native source required" not in negative.stderr:
        raise RuntimeError(suffix + " diagnostic/Native-source acceptance proof failed")
    entry["delivery_acceptance"] = {
        "case_id": entry["case_id"], "sets": ["full-train"],
        "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
        "script": "delivery_audit.py", "script_sha256": sha(SCRIPT),
        "command": " ".join([*base, "--diagnostic"]), "test_exit_code": positive.returncode,
        "test_log": str((area / "positive.log").relative_to(ROOT)), "test_log_sha256": sha(area / "positive.log"),
        "negative_command": " ".join(base), "negative_exit_code": negative.returncode,
        "negative_expected_error": "Original Native source required",
        "negative_log": str((area / "negative.log").relative_to(ROOT)),
        "negative_log_sha256": sha(area / "negative.log"),
    }
    print(suffix, "diagnostic accepted=false, Native-source guard rejected")
m["status"] = "partial_delivery_cpu_proven"
MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
