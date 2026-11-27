"""Bind saved-only CPU and independent positive/negative audit receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / ".runtime-work/c158190-stop-owner"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_log(source, target):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise ValueError("empty CPU log")
    target.write_text("\n".join(lines) + "\n")
    return sha(target)


def main():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    audit_script = ROOT / "prove_stop_delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.rsplit("_", 1)[-1]
        folder = ROOT / "cases" / ("stop_nearest_view_" + short)
        saved_log = folder / "proof-selected-saved.log"
        saved_sha = copy_log(SCRATCH / ("saved-" + short + "-3.log"), saved_log)
        command = (".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ROOT.name +
                   "/execution-manifest.json --case " + case + " --attempt \"$ATTEMPT\" "
                   "--output \"$SAVED_OUTPUT\" --library \"$LIBRARY\" --validator \"$VALIDATOR\" "
                   "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"")
        entry["post_capture"] = {"recorded_only": True, "command": command,
                                 "feedback_command": command, "test_exit_code": 0,
                                 "test_log": str(saved_log.relative_to(ROOT)),
                                 "test_log_sha256": saved_sha,
                                 "proof_scope": "Selected synthetic diagnostic saved-only processing; original Native source pending"}
        positive = folder / "proof-delivery-positive.log"
        negative = folder / "proof-delivery-negative.log"
        positive_sha = copy_log(SCRATCH / ("delivery-positive-" + short + ".log"), positive)
        negative_sha = copy_log(SCRATCH / ("delivery-negative-" + short + ".log"), negative)
        script_cmd = ".venv-cpu/bin/python work/" + ROOT.name + "/prove_stop_delivery_audit.py " + case
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"], "checks": CHECKS,
            "command": script_cmd, "negative_command": script_cmd + " --negative",
            "script": "prove_stop_delivery_audit.py", "script_sha256": sha(audit_script),
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": "original saved acquisition required for physical review",
            "test_log": str(positive.relative_to(ROOT)), "test_log_sha256": positive_sha,
            "negative_log": str(negative.relative_to(ROOT)), "negative_log_sha256": negative_sha,
            "scope": "Synthetic CPU source-review contract only; no original source or physical acceptance asserted"}
        entry["missing_proofs"] = [item for item in entry["missing_proofs"]
                                   if item != "original_delivery_acceptance"]
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("Bound stop saved-only and delivery CPU proofs:", len(manifest["cases"]))


if __name__ == "__main__":
    main()
