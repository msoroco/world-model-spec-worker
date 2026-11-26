"""Prove independent delivery acceptance on explicit synthetic documents."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SCRATCH = ROOT / ".runtime-work/c272352-nov26/delivery-diagnostic-v2"
SCRIPT = HERE / "delivery_audit.py"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(AID + "__")
        folder = SCRATCH / suffix
        folder.mkdir(exist_ok=False)
        bindings = {name + ".mkv": hashlib.sha256((case + name).encode()).hexdigest()
                    for name in CAMERAS}
        capture = {"case_id": case, "frame_count": 900, "full_decode": True,
                   "receipt_sha256": hashlib.sha256(case.encode()).hexdigest(),
                   "source_bindings": bindings, "diagnostic_fixture": True}
        write(folder / "diagnostic-capture-audit.json", capture)
        views = {name: {"video_sha256": bindings[name + ".mkv"],
                        "reviewer": "CPU protocol fixture",
                        "samples": [{"frame": 100, "ego_visible": True,
                                     "qualifying_rider_visible": True,
                                     "decoded_rgb_sha256": hashlib.sha256(
                                         (name + case).encode()).hexdigest()}]}
                 for name in CAMERAS}
        review = {"case_id": case, "capture_receipt_sha256": capture["receipt_sha256"],
                  "views": views, "legal_due_care": None,
                  "legal_safe_distance": None, "legal_safely_clear": None,
                  "legal_exception_213_217": None}
        positive = folder / "pixel-review.json"
        negative = folder / "pixel-review-missing-view.json"
        write(positive, review)
        write(negative, dict(review, views={name: value for name, value in views.items()
                                            if name != "approach"}))
        physical = HERE / ("physical-" + suffix + "-complete_motion.json")
        base = [sys.executable, str(SCRIPT), "--case", case,
                "--attempt", str(folder), "--physical", str(physical),
                "--diagnostic-fixture", "--review"]
        env = dict(os.environ,
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c272352-nov26/pipeline"),
                   TMPDIR=str(ROOT / ".runtime-work/c272352-nov26"))
        good = subprocess.run(base + [str(positive)], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bad = subprocess.run(base + [str(negative)], cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        good_log = HERE / ("proof-delivery-positive-" + suffix + ".log")
        bad_log = HERE / ("proof-delivery-negative-" + suffix + ".log")
        good_log.write_text(good.stdout.rstrip() + "\n")
        bad_log.write_text(bad.stdout.rstrip() + "\n")
        expected = "independent four-view pixel review missing"
        if good.returncode or bad.returncode == 0 or expected not in bad.stdout:
            raise ValueError("delivery positive/negative CPU protocol failed: " + suffix)
        receipt = {"case_id": case, "sets": ["full-test"],
                   "checks": ["native_source", "all_participants", "time_join",
                              "full_video_decode", "actual_pixels", "physical_completion"],
                   "test_exit_code": 0, "negative_exit_code": bad.returncode,
                   "negative_expected_error": expected,
                   "command": " ".join(base + [str(positive)]),
                   "negative_command": " ".join(base + [str(negative)]),
                   "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
                   "test_log": good_log.name, "test_log_sha256": sha(good_log),
                   "negative_log": bad_log.name, "negative_log_sha256": sha(bad_log),
                   "diagnostic_scope": "CPU protocol only; original Native pixels and human review remain required"}
        path = HERE / ("delivery-acceptance-" + suffix + ".json")
        write(path, receipt)
        entry["delivery_acceptance"] = receipt
        print("passed", suffix, flush=True)
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("independent delivery CPU proofs:", run())
