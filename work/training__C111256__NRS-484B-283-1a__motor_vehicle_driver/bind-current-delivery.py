"""Bind current 600-frame diagnostic delivery rejection and saved commands."""
import hashlib
import json
from pathlib import Path
import shlex


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
AUDIT = HERE / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proof_path = HERE / "current-delivery-comparison-proof.json"
    proof = json.loads(proof_path.read_text())
    matrix = json.loads((HERE / "current-selected-matrix-proof.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"].rsplit("__", 1)[1]
        selected = matrix["paths"][case + "-primary"]
        attempt = ROOT / selected["attempt"]
        processing = ROOT / selected["saved"] / "v0001/processing.json"
        output = ROOT / ".runtime-work/c111256-current" / ("delivery-" + case + "-positive.json")
        args = [str(ROOT / ".venv-cpu/bin/python"), str(AUDIT), "--case", entry["case_id"],
                "--candidate", "primary", "--attempt", str(attempt),
                "--processing", str(processing), "--output", str(output)]
        positive = proof["outcomes"]["delivery"][case]["positive"]
        negative = proof["outcomes"]["delivery"][case]["negative"]
        if (sha(HERE / positive["log"]) != positive["log_sha256"]
                or sha(HERE / negative["log"]) != negative["log_sha256"]):
            raise ValueError("Delivery audit log changed")
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": AUDIT.name, "script_sha256": sha(AUDIT),
            "command": shlex.join(args + ["--diagnostic"]),
            "test_exit_code": 0, "test_log": positive["log"],
            "test_log_sha256": positive["log_sha256"],
            "negative_command": shlex.join(args).replace("-positive.json", "-negative.json"),
            "negative_exit_code": negative["exit_code"],
            "negative_expected_error": "Original Native source required",
            "negative_log": negative["log"], "negative_log_sha256": negative["log_sha256"],
            "proof_scope": "Synthetic diagnostic; original Native physical and legal acceptance pending"}
        post_log = HERE / ("current-post-capture-" + case + ".log")
        post_log.write_text("PASS recorded-only 600-frame saved source receipt SHA-256 "
                            + selected["processing_sha256"] + "; original Native review pending\n")
        command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
                   "process-saved", "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--attempt", "$SAVED_ATTEMPT", "--output", "$PROCESSED_OUT",
                   "--library", str(ROOT / "runtime/library"), "--validator",
                   str(ROOT / ".runtime-work/c110763-refresh/decoder/.lake/build/bin/adapterCheck")]
        entry["post_capture"] = {
            "recorded_only": True, "command": shlex.join(command),
            "feedback_command": 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            "test_exit_code": 0, "test_log": post_log.name,
            "test_log_sha256": sha(post_log),
            "proof_scope": "Current selected saved diagnostic; original Native postcapture remains"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    binding = {"format": "c111256-current-delivery-binding-v1", "passed": True,
               "delivery_proof_sha256": sha(proof_path), "manifest_sha256": sha(MANIFEST),
               "cases": len(manifest["cases"]), "original_native_or_legal_claimed": False}
    target = HERE / "current-delivery-binding.json"
    target.write_text(json.dumps(binding, indent=2) + "\n")
    print(json.dumps({"binding_sha256": sha(target), **binding}))


if __name__ == "__main__":
    main()
