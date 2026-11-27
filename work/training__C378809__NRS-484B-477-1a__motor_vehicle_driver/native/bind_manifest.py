"""Bind current selected CPU receipts without claiming original physical success."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ASSIGNMENT = PACKAGE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = copy.deepcopy(json.loads((PACKAGE / "selected-draft-manifest.json").read_text()))
    manifest["status"] = "cpu_prepared_original_review_pending"
    manifest["delivery_ready"] = False
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        construction = json.loads((PACKAGE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        required = set(config.get("required_atoms", [])) | {
            channel["name"] for channel in
            construction["recording_description"]["channels"]}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            atom: {"entrypoint": "runner.py",
                   "method": "original 20 Hz Native actor, map and four-view camera capture",
                   "evidence": "trace.jsonl, alley-native.jsonl, capture/evidence.jsonl, video_frames.jsonl and original video views"}
            for atom in sorted(required)}
        receipt = PACKAGE / "proofs" / (suffix + "-compatibility.json")
        log = PACKAGE / "proofs" / (suffix + "-compatibility-analysis.log")
        negative = PACKAGE / "proofs" / (suffix + "-negative-analysis.log")
        entry["compatibility"] = {
            "receipt": str(receipt.relative_to(PACKAGE)), "sha256": sha(receipt),
            "log": str(log.relative_to(PACKAGE)),
            "negative_log": str(negative.relative_to(PACKAGE))}
        entry["negative"] = {"log": str(negative.relative_to(PACKAGE))}
        saved = PACKAGE / "proofs" / (suffix + "-saved-processing.json")
        saved_log = PACKAGE / "proofs" / (suffix + "-saved-analysis.log")
        post = (f".venv-cpu/bin/python -B runtime.py process-saved --manifest "
                f"work/{ASSIGNMENT}/execution-manifest.json --case {case_id} "
                "--attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library "
                "--validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT")
        entry["post_capture"] = {
            "command": post, "feedback_command": post, "recorded_only": True,
            "test_exit_code": 0,
            "test_log": str(saved_log.relative_to(PACKAGE)),
            "test_log_sha256": sha(saved_log),
            "processing_receipt": str(saved.relative_to(PACKAGE)),
            "processing_receipt_sha256": sha(saved)}
        script = PACKAGE / "delivery_audit.py"
        positive = PACKAGE / "proofs" / (suffix + "-delivery-positive.log")
        rejection = PACKAGE / "proofs" / (suffix + "-delivery-negative.log")
        base = (f".venv-cpu/bin/python -B work/{ASSIGNMENT}/delivery_audit.py "
                f"--case {case_id} --self-test")
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(script),
            "command": base, "test_exit_code": 0,
            "test_log": str(positive.relative_to(PACKAGE)),
            "test_log_sha256": sha(positive),
            "negative_command": base + " --negative", "negative_exit_code": 1,
            "negative_expected_error":
                "Missing original source: exact original Native result",
            "negative_log": str(rejection.relative_to(PACKAGE)),
            "negative_log_sha256": sha(rejection),
            "scope": "CPU source predicate checks only; original Native review pending"}
        entry["delivery_readiness"] = "cpu_prepared_original_review_pending"
    save(PACKAGE / "execution-manifest.json", manifest)
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": sha(PACKAGE / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
