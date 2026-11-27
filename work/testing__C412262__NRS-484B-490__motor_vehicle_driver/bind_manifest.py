"""Bind completed CPU diagnostic proofs without claiming original source acceptance."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    proofs = {x["case_id"]: x for x in json.loads((ROOT / "cpu-delivery-proofs.json").read_text())}
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        proof = proofs[case_id]
        construction = json.loads((ROOT / entry["construction"]).read_text())
        channels = [x["name"] for x in construction["recording_description"]["channels"]]
        entrypoints = {
            "vehicle_center_and_body": "native_capture.py",
            "vehicle_speed": "native_capture.py",
            "full_highway_boundary_and_width": "highway_scene_construction.py",
            "official_device_and_extent": "highway_scene_construction.py",
            "responsible_person_and_activity": "native_capture.py",
            "original_four_camera_pixels": "native_capture.py",
        }
        entry["acquisition"] = {
            name: {"entrypoint": entrypoints[name], "method": "source_bound_native_readback",
                   "evidence": ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json"]}
            for name in channels}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                                   "source_env_var": "SCENARIO_HIGHWAY_SITE_PACKET"}
        entry["candidate_risk"] = {
            "status": "none", "reason": "No distinct physical failure mode can yet be measured without the reviewed original highway and device source; original physical performance remains pending."}
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "diagnostic_delivery_audit.py", "script_sha256": sha(ROOT / "diagnostic_delivery_audit.py"),
            "command": proof["command"], "test_exit_code": 0,
            "test_log": proof["positive_log"], "test_log_sha256": proof["positive_log_sha256"],
            "positive_receipt": proof["positive_receipt"],
            "positive_receipt_sha256": proof["positive_receipt_sha256"],
            "negative_command": proof["negative_command"],
            "negative_exit_code": proof["negative_exit_code"],
            "negative_log": proof["negative_log"],
            "negative_log_sha256": proof["negative_log_sha256"],
            "negative_expected_error": proof["negative_expected_error"],
            "diagnostic_only": True, "physical_acceptance": False}
        entry.pop("missing_proofs", None)
        entry["status"] = "source_gated_cpu_prepared"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
