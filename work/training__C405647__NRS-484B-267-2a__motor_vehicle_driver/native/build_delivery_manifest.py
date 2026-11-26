"""Bind selected CPU proofs to a truthful partial delivery manifest."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    source = json.loads((FOLDER / "selected-current-runtime-manifest.json").read_text())
    cases = []
    for draft in source["cases"]:
        suffix = draft["case_id"][-1]
        proof = FOLDER / "native" / ("selected-" + suffix + "-proof")
        construction = FOLDER / draft["construction"]
        case = draft["case_id"]
        offline_log = FOLDER / "native" / ("selected-" + suffix + "-offline.log")
        audit_script = FOLDER / "native/delivery_audit.py"
        entry = dict(draft)
        entry["kind"] = "delivery"
        entry["acquisition"] = {"emergency_speed_and_lamps": {
            "entrypoint": "finalize.py", "method": "saved original emergency observation readback at 20 Hz",
            "evidence": "source-hashed emergency_observations.jsonl and camera frame join"}}
        fallback_path = FOLDER / "native/selected" / suffix / "fallback1/construction.json"
        if fallback_path.is_file():
            fallback = {"id": "fallback1",
                        "construction": str(fallback_path.relative_to(FOLDER)),
                        "construction_sha256": sha(fallback_path),
                        "trigger": {
                            "source": "Original Native 600-frame emergency_observations.jsonl and frame-map readback",
                            "metric": "first_pass_frame",
                            "failure_condition": "Primary original readback has no pass frame or first_pass_frame is later than frame 500; remeasure this faster emergency-vehicle fallback under the same physical review. Synthetic fixture timing is only an engineering diagnostic."},
                        "changed_knobs": ["other_vehicle_speed_mps"]}
            candidate_proof = FOLDER / "native/selected" / suffix / "fallback1/proof"
            offline = candidate_proof / "offline.log"
            compatibility = candidate_proof / "compatibility.json"
            if offline.is_file() and compatibility.is_file():
                fallback["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                                       "/selected-current-runtime-manifest.json --case " + case +
                                       " --candidate fallback1 --output .runtime-work/c405647-" + suffix + "-fallback1-offline-v2 --python $PWD/.venv-cpu/bin/python",
                                       "exit_code": 0, "construction_sha256": sha(fallback_path),
                                       "log": str(offline.relative_to(FOLDER)), "log_sha256": sha(offline)}
                fallback["compatibility"] = {"receipt": str(compatibility.relative_to(FOLDER)),
                                             "sha256": sha(compatibility),
                                             "log": str((candidate_proof / "analysis.log").relative_to(FOLDER)),
                                             "negative_log": str((candidate_proof / "negative.log").relative_to(FOLDER))}
            entry["candidates"] = [fallback]
        entry["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                            "/selected-current-runtime-manifest.json --case " + case +
                            " --output .runtime-work/c405647-selected-" + suffix + "-offline-v3",
                            "exit_code": 0, "construction_sha256": sha(construction),
                            "log": "native/selected-" + suffix + "-offline.log",
                            "log_sha256": sha(offline_log)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        physical = FOLDER / "native/physical-proof" / suffix / "proof.json"
        if physical.is_file():
            entry["physical_preparation"] = {"case_id": case,
                                             "receipt": str(physical.relative_to(FOLDER)),
                                             "sha256": sha(physical)}
        entry["compatibility"] = {"receipt": "native/selected-" + suffix + "-proof/compatibility.json",
                                   "sha256": sha(proof / "compatibility.json"),
                                   "log": "native/selected-" + suffix + "-proof/selected-analysis.log",
                                   "negative_log": "native/selected-" + suffix + "-proof/negative-analysis.log"}
        entry["negative"] = {"log": "native/selected-" + suffix + "-proof/negative-analysis.log"}
        entry["saved_processing"] = {"receipt": "native/selected-" + suffix + "-proof/processing.json",
                                     "sha256": sha(proof / "processing.json")}
        entry["post_capture"] = {"recorded_only": True,
                                 "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                                 "/execution-manifest.json --case " + case +
                                 " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR",
                                 "feedback_command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                                 "/execution-manifest.json --case " + case +
                                 " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR",
                                 "test_exit_code": 0,
                                 "test_log": "native/selected-" + suffix + "-proof/saved-analysis.log",
                                 "test_log_sha256": sha(proof / "saved-analysis.log")}
        negative = FOLDER / "native" / ("selected-" + suffix + "-delivery-negative.log")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "native/delivery_audit.py", "script_sha256": sha(audit_script),
            "command": ".venv-cpu/bin/python work/" + AID + "/native/delivery_audit.py --case " +
                       case + " --attempt $ATTEMPT --review $INDEPENDENT_REVIEW",
            "negative_command": ".venv-cpu/bin/python work/" + AID +
                                "/native/delivery_audit.py --case " + case +
                                " --attempt $DIAGNOSTIC_ATTEMPT --review $DIAGNOSTIC_REVIEW",
            "test_exit_code": 0,
            "test_log": "native/selected-" + suffix + "-delivery-positive.log",
            "test_log_sha256": sha(FOLDER / "native" / ("selected-" + suffix + "-delivery-positive.log")),
            "negative_exit_code": 1,
            "negative_expected_error": "Original source inventory incomplete",
            "negative_log": "native/selected-" + suffix + "-delivery-negative.log",
            "negative_log_sha256": sha(negative) if negative.is_file() else None}
        entry["delivery_readiness"] = "partial_original_source_and_positive_audit_pending"
        cases.append(entry)
    preparing = json.loads((FOLDER / "preparing-compatibility-manifest.json").read_text())
    for draft in preparing["cases"]:
        branch = draft["case_id"].split("__preparing_to_move__", 1)[1]
        proof = FOLDER / "native/preparing" / branch / "proof"
        construction = FOLDER / draft["construction"]
        physical = FOLDER / "native/physical-proof" / branch / "proof.json"
        audit_script = FOLDER / "native/preparing_source_audit.py"
        fallback_source = draft["candidates"][0]
        fallback_proof = FOLDER / "native/preparing" / branch / "fallback1/proof"
        alternate = dict(fallback_source)
        alternate.update(trigger={
            "source": "Original Native preparing observation and pixel-review frame join",
            "metric": "first_visible_frame",
            "failure_condition": "Primary frame-120 indication is not independently visible before ego reach; retry the earlier frame-100 indication under the same source review."},
            changed_knobs=["other_vehicle_start_frame"],
            offline={"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                     "/preparing-fallback-compatibility-manifest.json --case " + draft["case_id"] +
                     " --candidate fallback1 --output .runtime-work/c405647-" + branch +
                     "-fallback1-offline-v8", "exit_code": 0,
                     "construction_sha256": fallback_source["construction_sha256"],
                     "log": str((fallback_proof / "offline.log").relative_to(FOLDER)),
                     "log_sha256": sha(fallback_proof / "offline.log")},
            compatibility={"receipt": str((fallback_proof / "compatibility.json").relative_to(FOLDER)),
                           "sha256": sha(fallback_proof / "compatibility.json"),
                           "log": str((fallback_proof / "analysis.log").relative_to(FOLDER)),
                           "negative_log": str((fallback_proof / "negative.log").relative_to(FOLDER))})
        entry = dict(draft)
        entry.update(kind="delivery", candidate_risk={
            "status": "physical",
            "reason": "Original preparing indication, subject visibility, approach timing and four-camera coverage need Native readback"},
            candidates=[alternate],
            offline={"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                     "/native/preparing-cpu-manifest.json --case " + draft["case_id"] +
                     " --output .runtime-work/c405647-" + branch + "-primary-offline-v8",
                     "exit_code": 0, "construction_sha256": sha(construction),
                     "log": str((proof / "offline.log").relative_to(FOLDER)),
                     "log_sha256": sha(proof / "offline.log")},
            native_handoff={"python_env_var": "CARLA_PYTHON",
                            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            physical_preparation={"case_id": draft["case_id"],
                                  "receipt": str(physical.relative_to(FOLDER)),
                                  "sha256": sha(physical)},
            acquisition={"emergency_speed_and_lamps": {
                "entrypoint": "preparing_finalize.py", "method": "saved original preparing observations readback at 20 Hz",
                "evidence": "source-hashed preparing_observations.jsonl and camera frame join"}},
            negative={"log": str((proof / "negative.log").relative_to(FOLDER))},
            compatibility={"receipt": str((proof / "compatibility.json").relative_to(FOLDER)),
                           "sha256": sha(proof / "compatibility.json"),
                           "log": str((proof / "analysis.log").relative_to(FOLDER)),
                           "negative_log": str((proof / "negative.log").relative_to(FOLDER))},
            saved_processing={"receipt": str((proof / "processing.json").relative_to(FOLDER)),
                              "sha256": sha(proof / "processing.json")},
            post_capture={"recorded_only": True,
                          "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                          "/execution-manifest.json --case " + draft["case_id"] +
                          " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR",
                          "feedback_command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                          "/execution-manifest.json --case " + draft["case_id"] +
                          " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR",
                          "test_exit_code": 0,
                          "test_log": str((proof / "saved-analysis.log").relative_to(FOLDER)),
                          "test_log_sha256": sha(proof / "saved-analysis.log")},
            delivery_acceptance={"case_id": draft["case_id"], "sets": ["full-train"],
                                 "checks": ["native_source", "all_participants", "time_join",
                                            "full_video_decode", "actual_pixels", "physical_completion"],
                                 "script": str(audit_script.relative_to(FOLDER)),
                                 "script_sha256": sha(audit_script),
                                 "command": ".venv-cpu/bin/python work/" + AID +
                                 "/native/preparing_source_audit.py --case " + draft["case_id"] +
                                 " --attempt $ATTEMPT --review $INDEPENDENT_REVIEW",
                                 "negative_command": ".venv-cpu/bin/python work/" + AID +
                                 "/native/preparing_source_audit.py --case " + draft["case_id"] +
                                 " --attempt $DIAGNOSTIC_ATTEMPT --review $DIAGNOSTIC_REVIEW",
                                 "test_exit_code": 0,
                                 "test_log": str((proof / "delivery-positive.log").relative_to(FOLDER)),
                                 "test_log_sha256": sha(proof / "delivery-positive.log"),
                                 "negative_exit_code": 1,
                                 "negative_expected_error": "Native capture seal does not verify original acquisition",
                                 "negative_log": str((proof / "delivery-negative.log").relative_to(FOLDER)),
                                 "negative_log_sha256": sha(proof / "delivery-negative.log")},
            delivery_readiness="partial_original_source_and_independent_pixel_review_pending")
        cases.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "partial", "delivery_ready": False,
                "original_native_observed": False, "cases": cases}
    (FOLDER / "execution-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"cases": len(cases), "manifest_sha256": sha(FOLDER / "execution-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
