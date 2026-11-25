"""Bind saved-only and independent diagnostic delivery CPU proofs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c111610-nov24-owner"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    script = ROOT / "delivery_acceptance.py"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        version_id = "v0002" if suffix == "arrow_clear" else "v0001"
        version = SCRATCH / f"saved-output-{suffix}/{version_id}"
        receipt = json.loads((version / "processing.json").read_text())
        if (receipt.get("passed") is not True or
                receipt.get("case_id") != entry["case_id"] or
                receipt.get("analysis_revision", {}).get("construction_sha256") !=
                entry["construction_sha256"] or
                receipt.get("originals_preserved") is not True or
                receipt.get("physical_acceptance_claimed") is not False):
            raise ValueError("saved-only proof differs: " + suffix)
        saved_name = f"saved-processing-{suffix}-receipt.json"
        shutil.copyfile(version / "processing.json", ROOT / saved_name)
        saved_log = f"saved-processing-{suffix}.log"
        (ROOT / saved_log).write_text((SCRATCH / f"saved-process-{suffix}.log").read_text().rstrip() + "\n")
        command = (".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
                   "/execution-manifest.json --case " + entry["case_id"] +
                   " --attempt .runtime-work/c111610-nov24-owner/saved-attempt-" + suffix +
                   " --output .runtime-work/c111610-nov24-owner/saved-output-" + suffix +
                   " --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck")
        entry["post_capture"] = {
            "command": command, "feedback_command": command + " # inspect fresh vNNNN/feedback.json",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": saved_log, "test_log_sha256": sha(ROOT / saved_log),
            "receipt": saved_name, "receipt_sha256": sha(ROOT / saved_name)}
        positive = f"delivery-positive-{suffix}.log"
        negative = f"delivery-negative-{suffix}.log"
        if (json.loads((ROOT / positive).read_text()).get("software_checks_passed") is not True or
                "saved delivery site source missing" not in (ROOT / negative).read_text()):
            raise ValueError("independent delivery proof failed: " + suffix)
        base = (".venv-cpu/bin/python work/" + ROOT.name +
                "/delivery_acceptance.py --case " + entry["case_id"])
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["full-test"], "checks": CHECKS,
            "command": base + " --attempt .runtime-work/c111610-nov24-owner/saved-attempt-" + suffix +
                       " --processed .runtime-work/c111610-nov24-owner/saved-output-" + suffix + "/v0001 --diagnostic",
            "negative_command": base + " --attempt .runtime-work/c111610-nov24-owner/delivery-negative-" + suffix +
                                " --processed .runtime-work/c111610-nov24-owner/saved-output-" + suffix + "/v0001 --diagnostic",
            "script": script.name, "script_sha256": sha(script),
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "saved delivery site source missing",
            "test_log": positive, "test_log_sha256": sha(ROOT / positive),
            "negative_log": negative, "negative_log_sha256": sha(ROOT / negative),
            "scope": "synthetic diagnostic software proof; original physical and legal acceptance unclaimed"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("bound", bind(), "saved-only and independent delivery proofs")
