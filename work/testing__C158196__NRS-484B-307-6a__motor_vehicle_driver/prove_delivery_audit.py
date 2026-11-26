"""Prove independent delivery protocol on marked synthetic CPU documents."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from package_spec import AID, CAMERA_NAMES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work" / "c158196-owner-nov26" / "signal-delivery-diagnostic-v2"
SCRIPT = HERE / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    cases = json.loads((HERE / "case-plan.json").read_text())["cases"]
    for case in cases:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(AID + "__")
        root = SCRATCH / suffix
        if root.exists():
            raise ValueError("retain previous delivery diagnostic fixture")
        root.mkdir()
        bindings = {name + ".mkv": hashlib.sha256((case_id + name).encode()).hexdigest()
                    for name in CAMERA_NAMES}
        capture = {"case_id": case_id, "frame_count": 900, "full_decode": True,
                   "receipt_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                   "source_bindings": bindings}
        write(root / "diagnostic-capture-audit.json", capture)
        views = {name: {"video_sha256": bindings[name + ".mkv"],
                        "reviewer": "CPU protocol fixture",
                        "samples": [{"frame": 100, "ego_visible": True,
                                     "selected_facing_signal_visible": True,
                                     "decoded_rgb_sha256": hashlib.sha256((name + case_id).encode()).hexdigest()}]}
                 for name in CAMERA_NAMES}
        review = {"case_id": case_id, "capture_receipt_sha256": capture["receipt_sha256"],
                  "views": views, "legal_warning_interpretation": None,
                  "legal_entry_interpretation": None, "legal_immediately_thereafter": None}
        positive = root / "pixel-review.json"
        write(positive, review)
        negative = root / "pixel-review-missing-view.json"
        write(negative, dict(review, views={k: v for k, v in views.items() if k != "approach"}))
        physical = HERE / "proofs" / "physical" / suffix / "complete_motion-result.json"
        if not physical.is_file():
            raise ValueError("physical CPU result missing: " + suffix)
        base = [sys.executable, str(SCRIPT), "--case", case_id,
                "--attempt", str(root), "--physical", str(physical),
                "--diagnostic-fixture", "--review"]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
        good = subprocess.run(base + [str(positive)], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bad = subprocess.run(base + [str(negative)], cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        good_log = HERE / ("proof-delivery-positive-" + suffix + ".log")
        bad_log = HERE / ("proof-delivery-negative-" + suffix + ".log")
        good_log.write_text(good.stdout.rstrip() + "\n")
        bad_log.write_text(bad.stdout.rstrip() + "\n")
        if good.returncode or bad.returncode == 0 or "independent pixel review missing four views" not in bad.stdout:
            raise ValueError("independent delivery protocol proof failed: " + suffix)
        receipt = {"case_id": case_id, "sets": ["demo-test", "full-test"],
                   "checks": ["native_source", "all_participants", "time_join",
                              "full_video_decode", "actual_pixels", "physical_completion"],
                   "test_exit_code": 0, "negative_exit_code": bad.returncode,
                   "negative_expected_error": "independent pixel review missing four views",
                   "command": " ".join(base + [str(positive)]),
                   "negative_command": " ".join(base + [str(negative)]),
                   "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
                   "test_log": good_log.name, "test_log_sha256": sha(good_log),
                   "negative_log": bad_log.name, "negative_log_sha256": sha(bad_log),
                   "diagnostic_scope": "CPU protocol only; original Native evidence and human pixel review required on GPU"}
        write(HERE / ("delivery-acceptance-" + suffix + ".json"), receipt)
    return len(cases)


if __name__ == "__main__":
    print("independent delivery CPU proofs:", run())
