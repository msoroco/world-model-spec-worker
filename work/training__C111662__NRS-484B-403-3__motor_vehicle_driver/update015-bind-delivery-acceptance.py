"""Bind exact CPU delivery-auditor proofs to selected C111662 cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
manifest_path = ROOT / "execution-manifest.json"
proof = json.loads((ROOT / "update015-delivery-auditor-cpu-proof.json").read_text())
manifest = json.loads(manifest_path.read_text())
if proof.get("passed") is not True or proof.get("original_native_observed") is not False:
    raise ValueError("Expected CPU-only independent delivery audit proof")
positives = {row["case_id"]: row for row in proof["positive_cases"]}
negatives = {row["case_id"]: row for row in proof["negative_cases"]}
cases = {row["case_id"] for row in manifest["cases"]}
if cases != set(positives) or cases != set(negatives):
    raise ValueError("Proof case set differs from selected delivery cases")
for entry in manifest["cases"]:
    case = entry["case_id"]
    positive, negative = positives[case], negatives[case]
    for row in (positive, negative):
        path = ROOT / row["log"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["log_sha256"]:
            raise ValueError("Stale delivery audit proof log")
    entry["delivery_acceptance"] = {
        "case_id": case, "sets": ["full-train"],
        "checks": ["native_source", "all_participants", "time_join",
                   "full_video_decode", "actual_pixels", "physical_completion"],
        "script": proof["auditor"], "script_sha256": proof["auditor_sha256"],
        "command": " ".join(positive["command"]),
        "test_exit_code": positive["exit_code"], "test_log": positive["log"],
        "test_log_sha256": positive["log_sha256"],
        "negative_command": " ".join(negative["command"]),
        "negative_exit_code": negative["exit_code"],
        "negative_log": negative["log"],
        "negative_log_sha256": negative["log_sha256"],
        "negative_expected_error": negative["failure"],
        "scope": "synthetic CPU mechanics; original capture still unverified"}
    triggers = {
        "fallback1": ("observed turn speed and heading reversal",
                      "primary requested path does not complete a measured turn at its speed"),
        "fallback2": ("decoded vehicle and road-reference pixel coverage",
                      "primary camera policy fails source-bound visibility review"),
        "fallback3": ("consecutive pre-turn frames before the observed reversal",
                      "primary pre-turn interval is too short for complete source review"),
    }
    for candidate in entry["candidates"]:
        metric, failure = triggers[candidate["id"]]
        candidate["trigger"] = {
            "source": "saved Native actors, frame map and four original camera streams",
            "metric": metric, "failure_condition": failure}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"bound_selected_cases": len(cases), "original_native_observed": False,
                  "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))
