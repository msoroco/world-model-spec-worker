"""Bind the paired CPU-proved constructions to an exact selected draft."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def receipt(path):
    return {"path": path, "sha256": digest(path)}


def main():
    draft = json.loads((ROOT / "v2-fallback-draft-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = []
    for index, entry in enumerate(draft["cases"], 1):
        witness = f"witness_{index}"
        primary = f"selected-v2/proofs/witness{index}-primary"
        fallback = f"selected-v2/proofs/witness{index}-fallback1"
        case = dict(entry)
        case["kind"] = "delivery"
        case["preparation_status"] = "selected_cpu_proofs_physical_unverified"
        case["primary_proofs"] = {
            "offline": receipt(f"{primary}/offline.log"),
            "compatibility": receipt(f"{primary}/compatibility.json"),
            "missing_source_negative": receipt(f"{primary}/negative-analysis.log"),
            "recorded_only_processing": receipt(f"{primary}/processing.json"),
        }
        case["offline"] = {
            "command": f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/selected-v2-manifest.json --case {case["case_id"]} --output "$OUTPUT"',
            "construction_sha256": case["construction_sha256"],
            "exit_code": 0,
            "log": case["primary_proofs"]["offline"]["path"],
            "log_sha256": case["primary_proofs"]["offline"]["sha256"],
        }
        case["compatibility"] = {
            "receipt": case["primary_proofs"]["compatibility"]["path"],
            "sha256": case["primary_proofs"]["compatibility"]["sha256"],
            "log": f"{primary}/analysis.log",
            "negative_log": f"{primary}/negative-analysis.log",
        }
        case["negative"] = {"log": f"{primary}/negative-analysis.log"}
        case["acquisition"] = {
            "ru.motor_vehicle": {"entrypoint": "runner.py", "method": "Native ego spawn and actor-type readback", "evidence": "synthetic CPU fixture only; original Native actor proof pending"},
            "kin.position": {"entrypoint": "runner.py", "method": "Native sampled transform and saved route join", "evidence": "synthetic CPU fixture only; original Native pose proof pending"},
            "kin.heading": {"entrypoint": "runner.py", "method": "Native sampled heading and saved route join", "evidence": "synthetic CPU fixture only; original Native heading proof pending"},
            "roundabout_route": {"entrypoint": "finalize.py", "method": "Recorded route samples and original road/lane readback", "evidence": "synthetic CPU fixture only; original Native route and physical review pending"},
        }
        case["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT",
        }
        physical = receipt(f"selected-v2/physical/witness{index}/proof.json")
        case["physical_preparation"] = {"receipt": physical["path"],
                                        "sha256": physical["sha256"]}
        candidate = dict(case["candidates"][0])
        candidate["proofs"] = {
            "offline": receipt(f"{fallback}/offline.log"),
            "compatibility": receipt(f"{fallback}/compatibility.json"),
            "missing_source_negative": receipt(f"{fallback}/negative-analysis.log"),
            "recorded_only_processing": receipt(f"{fallback}/processing.json"),
        }
        candidate["offline"] = {
            "command": f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/selected-v2-manifest.json --case {case["case_id"]} --candidate fallback1 --output "$OUTPUT"',
            "construction_sha256": candidate["construction_sha256"],
            "exit_code": 0,
            "log": candidate["proofs"]["offline"]["path"],
            "log_sha256": candidate["proofs"]["offline"]["sha256"],
        }
        candidate["compatibility"] = {
            "receipt": candidate["proofs"]["compatibility"]["path"],
            "sha256": candidate["proofs"]["compatibility"]["sha256"],
            "log": f"{fallback}/analysis.log",
            "negative_log": f"{fallback}/negative-analysis.log",
        }
        case["candidates"] = [candidate]
        case["post_capture"] = {
            "recorded_only": True,
            "command": f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/selected-v2-manifest.json --case {case["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR"',
            "feedback_command": f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/selected-v2-manifest.json --case {case["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR"',
            "test_log": case["primary_proofs"]["recorded_only_processing"]["path"],
            "test_log_sha256": case["primary_proofs"]["recorded_only_processing"]["sha256"],
            "test_exit_code": 0,
            "diagnostic_receipt": case["primary_proofs"]["recorded_only_processing"],
        }
        positive = receipt(f"selected-v2/proofs/witness{index}-delivery-positive.log")
        negative = receipt(f"selected-v2/proofs/witness{index}-delivery-negative.log")
        case["delivery_acceptance"] = {
            "case_id": case["case_id"],
            "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "selected-v2/delivery_audit.py",
            "script_sha256": digest("selected-v2/delivery_audit.py"),
            "command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected-v2/delivery_audit.py --case {case["case_id"]} --cpu-test positive',
            "test_exit_code": 0,
            "test_log": positive["path"],
            "test_log_sha256": positive["sha256"],
            "negative_command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected-v2/delivery_audit.py --case {case["case_id"]} --cpu-test negative',
            "negative_exit_code": 1,
            "negative_expected_error": "Physical review references another original camera: driver_reference",
            "negative_log": negative["path"],
            "negative_log_sha256": negative["sha256"],
            "original_command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected-v2/delivery_audit.py --case {case["case_id"]} --attempt "$ATTEMPT" --review "$REVIEW_RECEIPT"',
            "physical_acceptance_claimed": False,
        }
        selected.append(case)
    output = {
        "format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
        "status": "selected_cpu_partial_physical_unverified",
        "selected_case_ids": [case["case_id"] for case in selected],
        "comparisons": [{
            **plan["comparisons"][0],
            "fixed_conditions": [
                "same frozen cell, law, actor, authored road and non-target actors",
                "same 30-second 20-Hz four-camera recording and source-packet contract",
                "same controller source, requested speed and capture/finalizer implementation",
                "same original frame/time grid; route position, heading and phase may respond to the requested circulating lane",
            ],
            "isolation_audit": "selected-v2/audit.json",
            "original_comparison_audit": {
                "script": "selected-v2/comparison_audit.py",
                "script_sha256": digest("selected-v2/comparison_audit.py"),
                "positive_cpu_test": receipt("selected-v2/comparison-positive.log"),
                "negative_cpu_test": receipt("selected-v2/comparison-negative.log"),
                "negative_expected_error": "Comparison fixed condition differs: road_sha256",
                "original_command": f'.venv-cpu/bin/python work/{ASSIGNMENT}/selected-v2/comparison_audit.py --attempt1 "$ATTEMPT_1" --attempt2 "$ATTEMPT_2" --review1 "$REVIEW_1" --review2 "$REVIEW_2"',
                "physical_acceptance_claimed": False,
            },
        }],
        "semantic_proposal_index": receipt("proposals/semantic-index.json"),
        "cases": selected,
        "independent_cpu_audits": [
            receipt("v2-native-draft/audit.json"),
            receipt("v2-fallback-draft/audit.json"),
            receipt("v2-native-draft/fake-native-test.log"),
        ],
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }
    (ROOT / "selected-v2-manifest.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    )
    print(digest("selected-v2-manifest.json"))


if __name__ == "__main__":
    main()
