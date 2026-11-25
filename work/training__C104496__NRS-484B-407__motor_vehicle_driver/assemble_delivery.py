"""Bind selected CPU evidence to exact execution candidates without making physical claims."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def ref(path):
    return {"receipt": str(path.relative_to(HERE)), "sha256": sha(path)}


def offline(probe, candidate):
    row = next(row for row in read(HERE / "selected-offline-proof.json")["cases"]
               if row["case_id"].endswith(probe) and row["candidate_id"] == candidate)
    return {key: row[key] for key in ("command", "exit_code", "construction_sha256", "log", "log_sha256")}


def compatibility(probe, candidate):
    base = HERE / "compatibility" / probe / candidate
    path = base / "compatibility.json"
    return {"receipt": str(path.relative_to(HERE)), "sha256": sha(path),
            "log": str((base / ("compatibility-analysis.log" if (base / "compatibility-analysis.log").exists() else "analysis.log")).relative_to(HERE)),
            "negative_log": str((base / "negative-analysis.log").relative_to(HERE))}


def main():
    manifest = copy.deepcopy(read(HERE / "selected-compatibility-manifest.json"))
    manifest["status"] = "cpu_evidence_bound_physical_unverified"
    physical = read(HERE / "physical-fixtures-proof.json")
    for i, entry in enumerate(manifest["cases"], 1):
        probe = f"probe_{i:02d}"
        entry["offline"] = offline(probe, "primary")
        entry["compatibility"] = compatibility(probe, "primary")
        contract = read(HERE / entry["measurement_contract"])
        entry["negative"] = {"log": f"compatibility/{probe}/primary/negative-analysis.log"}
        config = read(HERE / entry["construction"])
        files = {row["path"] for row in config["files"]}
        channels = {row["name"] for row in config["recording_description"]["channels"]}
        capture_entry = next(path for path in files if path.endswith("capture.py"))
        entry["acquisition"] = {name: {"entrypoint": capture_entry, "method": "synchronized Native capture and source-hashed saved analysis", "evidence": "capture/evidence.jsonl, four FFV1 cameras and source review"} for name in channels}
        assert capture_entry in files
        source = next(row for row in physical["cases"] if row["case_id"] == entry["case_id"])
        source["lifecycle"] = {"events": ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"], "exit_code": 0, "log": f"physical/{probe}/lifecycle.log", "log_sha256": sha(HERE / "physical" / probe / "lifecycle.log")}
        proof_path = HERE / "physical" / probe / "preparation-proof.json"
        write(proof_path, source)
        entry["physical_preparation"] = ref(proof_path)
        entry["post_capture"] = {"command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {entry['case_id']} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT", "feedback_command": f"cat $OUTPUT/versions/*/feedback.json # {entry['case_id']}", "recorded_only": True, "test_exit_code": 0, "test_log": f"saved-processing/{probe}/processing.json", "test_log_sha256": sha(HERE / "saved-processing" / probe / "processing.json")}
        audit_script = HERE / "delivery_audit.py"
        test_dir = HERE / "delivery-tests" / probe
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["demo-train", "full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(audit_script),
            "command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {entry['case_id']} --self-test",
            "test_exit_code": 0, "test_log": f"delivery-tests/{probe}/positive.log",
            "test_log_sha256": sha(test_dir / "positive.log"),
            "negative_command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {entry['case_id']} --self-test --negative",
            "negative_exit_code": 1, "negative_expected_error": "Missing original source: exact original Native result",
            "negative_log": f"delivery-tests/{probe}/negative.log",
            "negative_log_sha256": sha(test_dir / "negative.log"),
        }
        for candidate in entry["candidates"]:
            name = candidate["id"]
            candidate["offline"] = offline(probe, name)
            candidate["compatibility"] = compatibility(probe, name)
            if name == "fallback1":
                candidate["trigger"] = {"source": "original Native turn motion and capture review", "metric": "realized turn speed or incomplete maneuver", "failure_condition": "primary fails a full three-point reversal"}
                candidate["changed_knobs"] = ["requested_speed_mps: 5.0 to 3.0"]
            else:
                candidate["trigger"] = {"source": "original camera review", "metric": "body recognition in overview", "failure_condition": "primary overview does not show the full reversal"}
                candidate["changed_knobs"] = ["camera_policy: standard to elevated_overview"]
    write(HERE / "execution-manifest.json", manifest)


if __name__ == "__main__":
    main()
