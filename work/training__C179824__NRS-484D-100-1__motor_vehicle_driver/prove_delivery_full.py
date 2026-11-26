"""Run exact positive and missing-source CPU predicates for every selected case."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
SCRIPT = ROOT / "delivery_audit_full.py"
MANIFEST = ROOT / "execution-manifest.json"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_log(text):
    return "\n".join(line.rstrip() for line in text.rstrip().splitlines()) + "\n"


data = json.loads(MANIFEST.read_text())
for entry in data["cases"]:
    case = entry["case_id"]
    suffix = case.split("__")[-1]
    target = ROOT / "delivery-proofs" / suffix
    target.mkdir(parents=True, exist_ok=True)
    commands = {}
    for negative in (False, True):
        argv = [sys.executable, "-B", str(SCRIPT), "--case", case, "--self-test"]
        if negative:
            argv.append("--negative")
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                cwd=ROOT.parents[1], env=os.environ.copy(), timeout=120)
        log = target / ("negative.log" if negative else "positive.log")
        log.write_text(clean_log(result.stdout))
        if negative:
            assert result.returncode != 0 and "Person and vehicle discernibility require separate original pixel review" in result.stdout
        else:
            assert result.returncode == 0, result.stdout
        commands["negative" if negative else "positive"] = (" ".join(argv), result.returncode, log)
    positive, negative = commands["positive"], commands["negative"]
    entry["delivery_acceptance"] = {
        "case_id": case, "sets": ["full-train"], "checks": CHECKS,
        "script": "delivery_audit_full.py", "script_sha256": sha(SCRIPT),
        "command": positive[0], "test_exit_code": positive[1],
        "test_log": str(positive[2].relative_to(ROOT)), "test_log_sha256": sha(positive[2]),
        "negative_command": negative[0], "negative_exit_code": negative[1],
        "negative_expected_error": "Person and vehicle discernibility require separate original pixel review",
        "negative_log": str(negative[2].relative_to(ROOT)), "negative_log_sha256": sha(negative[2]),
        "scope": "source predicate CPU proof only; original Native capture not observed",
    }
MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
print(json.dumps({"selected_delivery_cpu_proofs": len(data["cases"]),
                  "original_native_observed": False}, sort_keys=True))
