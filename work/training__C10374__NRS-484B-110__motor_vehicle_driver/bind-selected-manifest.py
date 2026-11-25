"""Bind the six source-shaped CPU probes to their exact planned delivery cases.

This is a staging operation. It does not claim physical preparation or acceptance.
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(name):
    return f"selected-proofs/{name}"


def source(name):
    path = HERE / rel(name)
    return rel(name), digest(path)


def candidate(case, suffix, candidate_id):
    stem = f"condition-{suffix}-{candidate_id}"
    proof = json.loads((HERE / rel(f"{stem}-proof.json")).read_text())
    construction = f"selected-current-v2-condition_{suffix}"
    if candidate_id != "primary":
        construction += f"-{candidate_id}"
    construction += "-construction.json"
    assert proof["case_id"] == case
    assert proof["candidate_id"] == candidate_id
    assert proof["construction_sha256"] == digest(HERE / construction)
    compatibility, compatibility_hash = source(f"{stem}-compatibility.json")
    analysis, _ = source(f"{stem}-compatibility-analysis.log")
    negative, _ = source(f"{stem}-negative-analysis.log")
    offline, offline_hash = source(f"{stem}-offline.log")
    saved, saved_hash = source(f"{stem}-saved-processing.json")
    select = "primary" if candidate_id == "primary" else candidate_id
    probe = f"selected-current-v2-condition_{suffix}"
    if candidate_id != "primary":
        probe += f"-{candidate_id}"
    probe += "-probe-manifest.json"
    command = (f".venv-cpu/bin/python runtime.py offline --manifest work/{AID}/{probe} "
               f"--case {case} --candidate {select} --output .runtime-work/c10374-selected-{stem}-offline")
    result = {
        "id": candidate_id,
        "construction": construction,
        "construction_sha256": proof["construction_sha256"],
        "offline": {"command": command, "exit_code": 0, "construction_sha256": proof["construction_sha256"],
                    "log": offline, "log_sha256": offline_hash},
        "compatibility": {"receipt": compatibility, "sha256": compatibility_hash,
                          "log": analysis, "negative_log": negative},
        "post_capture_proof": {"receipt": saved, "sha256": saved_hash},
    }
    if candidate_id != "primary":
        if candidate_id == "fallback1":
            trigger = {"source": "original Native route and body samples", "metric": "planned path completion",
                       "failure_condition": "primary route fails to complete the planned path"}
            knobs = ["requested_ego_speed_mps: 8.0 to 5.0"]
        else:
            trigger = {"source": "original four camera sources", "metric": "vehicle and zone boundary visibility",
                       "failure_condition": "primary camera geometry cannot show body and boundary together"}
            knobs = ["camera_policy: standard to elevated_overview"]
        result.update(trigger=trigger, changed_knobs=knobs)
    return result


def build():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    entries = []
    for suffix in ("a", "b"):
        case = next(c["case_id"] for c in proposal["cases"] if c["case_id"].endswith(f"condition_{suffix}"))
        primary = candidate(case, suffix, "primary")
        fallbacks = [candidate(case, suffix, name) for name in ("fallback1", "fallback2")]
        entry = {
            "case_id": case,
            "kind": "delivery",
            "construction": primary["construction"],
            "construction_sha256": primary["construction_sha256"],
            "candidate_risk": {"status": "physical", "reason": "Original route completion and zone/body visibility require review"},
            "candidates": fallbacks,
            "offline": primary["offline"],
            "compatibility": primary["compatibility"],
            "negative": {"log": primary["compatibility"]["negative_log"]},
            "measurement_contract": f"current-runtime-v2-condition_{suffix}-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "finalize.py", "output_schema": "c10374-source-analysis-v2"},
            "acquisition": {
                "kin.speed": {"entrypoint": "capture.py", "method": "sample original Native ego velocity at each frame",
                              "evidence": "native-raw-actors.jsonl joined to capture/evidence.jsonl"},
                "zone_body": {"entrypoint": "capture.py", "method": "sample eight original Native ego bounding vertices at each frame",
                              "evidence": "native-raw-actors.jsonl joined to native-map-readback.json"},
            },
            "fixture_recipe": f"work/{AID}/current-runtime-v2-condition_{suffix}-recipe.json",
            "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            "physical_preparation": {"receipt": f"physical/condition-{suffix}/preparation-proof.json",
                                     "sha256": digest(HERE / f"physical/condition-{suffix}/preparation-proof.json")},
            "delivery_acceptance": {
                "case_id": case, "sets": ["full-train"],
                "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                           "actual_pixels", "physical_completion"],
                "script": "delivery_audit.py", "script_sha256": digest(HERE / "delivery_audit.py"),
                "command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case} --self-test",
                "test_exit_code": 0, "test_log": f"audits/condition-{suffix}/positive.log",
                "test_log_sha256": digest(HERE / f"audits/condition-{suffix}/positive.log"),
                "negative_command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case} --self-test --negative",
                "negative_exit_code": 1,
                "negative_expected_error": "Missing original source: exact original Native result",
                "negative_log": f"audits/condition-{suffix}/negative.log",
                "negative_log_sha256": digest(HERE / f"audits/condition-{suffix}/negative.log"),
            },
            "post_capture": {"command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT",
                             "feedback_command": f"cat $OUTPUT/versions/*/feedback.json # {case}",
                             "recorded_only": True, "test_exit_code": 0,
                             "test_log": primary["post_capture_proof"]["receipt"],
                             "test_log_sha256": primary["post_capture_proof"]["sha256"]},
        }
        entries.append(entry)
    result = {"format": "worker-execution-manifest", "assignment_id": AID,
              "runtime_manifest_sha256": digest(REPO / "runtime/SOURCE-MANIFEST.json"),
              "status": "selected_delivery_proofs_pending", "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    build()
