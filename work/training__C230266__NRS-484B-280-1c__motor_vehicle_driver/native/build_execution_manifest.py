"""Bind 22 exact selected cases to completed CPU preparation proofs."""

import hashlib
import json
import os
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_map(path, key):
    return {row["case_id"]: row for row in read(path)[key]}


def main():
    preflight = read(ROOT / "selected-preflight-manifest.json")
    offline = row_map(ROOT / "selected-offline/index.json", "checks")
    compatible = row_map(ROOT / "compatibility/index.json", "passed")
    saved = row_map(ROOT / "recorded-only/index.json", "passed")
    audit = row_map(ROOT / "delivery-audit/index.json", "cases")
    current_preflight_hash = sha(ROOT / "selected-preflight-manifest.json")
    entries = []
    for source in preflight["cases"]:
        entry = dict(source)
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        off, com, rec, aud = (index[case] for index in (offline, compatible, saved, audit))
        if (off["construction_sha256"] != entry["construction_sha256"] or
                rec["construction_sha256"] != entry["construction_sha256"] or
                rec.get("manifest_sha256") != current_preflight_hash):
            raise ValueError("Stale exact-case CPU proof: " + suffix)
        com_receipt = ROOT / com["receipt"]
        if (sha(com_receipt) != com["receipt_sha256"] or
                read(com_receipt)["construction_sha256"] != entry["construction_sha256"]):
            raise ValueError("Stale selected compatibility receipt: " + suffix)
        parts = shlex.split(com["command"])
        attempt = Path(parts[parts.index("--output") + 1])
        selection = read(attempt / "candidate-selection.json")
        if selection.get("manifest_sha256") != current_preflight_hash:
            raise ValueError("Compatibility fixture binds another manifest: " + suffix)
        physical = ROOT / "physical" / suffix / "receipt.json"
        if read(physical)["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("Stale physical outcome proof: " + suffix)
        proof_path = ROOT / rec["proof"]
        proof = read(proof_path)
        if (sha(proof_path) != rec["proof_sha256"] or
                proof.get("test_exit_code") != 0 or
                proof.get("manifest_sha256") != current_preflight_hash):
            raise ValueError("Missing current saved-only proof: " + suffix)
        entry["candidate_risk"] = {
            "status": "none",
            "reason": "No permissible alternate changes the original driver-observation or statutory-position source needed here while preserving the exact four-camera, 600-frame comparison contract; missing original evidence requires a new Native attempt and independent review, not a substituted construction."
        }
        entry["candidates"] = []
        entry["offline"] = off
        entry["compatibility"] = {"receipt": com["receipt"], "sha256": com["receipt_sha256"],
                                  "log": com["analysis_log"],
                                  "negative_log": com["negative_log"]}
        entry["negative"] = {"log": com["negative_log"],
                             "log_sha256": com["negative_sha256"]}
        entry["physical_preparation"] = {
            "receipt": str(physical.relative_to(ROOT)), "sha256": sha(physical)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            "kin.position": {"entrypoint": "runner.py", "method": "Original Native ego and pedestrian actor transforms joined by frame", "evidence": ["pedestrian-caution-trace.jsonl", "video_frames.jsonl"]},
            "kin.speed": {"entrypoint": "runner.py", "method": "Original Native actor velocity per 20-Hz frame", "evidence": ["pedestrian-caution-trace.jsonl"]},
            "ru.pedestrian": {"entrypoint": "runner.py", "method": "Original pedestrian actor ID and independent classification source", "evidence": ["context-survey.json", "pedestrian-source-review.jsonl"]},
            "native_vehicle_pedestrian_pose_and_control": {"entrypoint": "runner.py", "method": "Original pose, requested control and source-review join", "evidence": ["pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl", "video_frames.jsonl"]},
            "four_camera_video": {"entrypoint": "runner.py", "method": "Four original RGB streams, synchronized through Native frame map", "evidence": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv", "video_frames.jsonl"]}
        }
        entry["post_capture"] = {
            "recorded_only": True,
            "command": "runtime.py process-saved --manifest work/" + preflight["assignment_id"] + "/execution-manifest.json --case " + case + " --attempt $ORIGINAL_ATTEMPT --output $DERIVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR",
            "feedback_command": "test -f $DERIVED_OUTPUT/v0001/feedback.json && cat $DERIVED_OUTPUT/v0001/feedback.json",
            "test_exit_code": proof["test_exit_code"],
            "test_log": proof["test_log"],
            "test_log_sha256": proof["test_log_sha256"]}
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            **{key: aud[key] for key in ("script", "script_sha256", "command",
                                       "test_exit_code", "test_log", "test_log_sha256",
                                       "negative_command", "negative_exit_code",
                                       "negative_expected_error", "negative_log",
                                       "negative_log_sha256")}}
        entry["preparation_status"] = "cpu_proven_original_delivery_pending"
        entry["delivery_readiness"] = "cpu_prepared_original_capture_pending"
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": preflight["assignment_id"],
                "runtime_manifest_sha256": preflight["runtime_manifest_sha256"],
                "cases": entries}
    destination = ROOT / "execution-manifest.json"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / "nrs280-execution-manifest.staging"
    stage.write_text(json.dumps(manifest, indent=2) + "\n")
    os.replace(stage, destination)
    print(json.dumps({"exact_cases": len(entries), "manifest_sha256": sha(destination)}))


if __name__ == "__main__":
    main()
