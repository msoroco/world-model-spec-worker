"""Bind exact C10365 cases to independently returned CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(relative):
    return relative, sha(HERE / relative)


def candidate(suffix, name):
    case = AID + "__probe_" + suffix
    construction = f"native/officer/selected-constructions/probe_{suffix}-{name}.json"
    construction_hash = sha(HERE / construction)
    stem = f"selected-proofs/probe_{suffix}-{name}"
    compatibility, compatibility_hash = reference(stem + "-compatibility.json")
    analysis, _ = reference(stem + "-compatibility-analysis.log")
    negative, _ = reference(stem + "-negative-analysis.log")
    offline, offline_hash = reference(stem + "-offline.log")
    if name == "primary":
        probe_manifest = "selected-probe-manifest.json"
    else:
        probe_manifest = f"selected-probe_{suffix}-{name}-manifest.json"
    command = (f".venv-cpu/bin/python runtime.py offline --manifest work/{AID}/{probe_manifest} "
               f"--case {case} --candidate {name} --output .runtime-work/c10365-final-probe_{suffix}-{name}-offline")
    result = {"id": name, "construction": construction,
              "construction_sha256": construction_hash,
              "offline": {"command": command, "exit_code": 0,
                          "construction_sha256": construction_hash,
                          "log": offline, "log_sha256": offline_hash},
              "compatibility": {"receipt": compatibility, "sha256": compatibility_hash,
                                "log": analysis, "negative_log": negative},
              "fixture_recipe": f"work/{AID}/native/officer/selected-recipes/probe_{suffix}-{name}.json"}
    if name == "fallback1":
        result.update(trigger={"source": "original Native rider speed and route samples",
                               "metric": "planned stop/crossing response completion",
                               "failure_condition": "primary route does not complete the requested device response"},
                      changed_knobs=["requested_speed_mps: 4.0 to 2.5", "requested-tracks speed profile"])
    elif name == "fallback2":
        result.update(trigger={"source": "original four camera streams",
                               "metric": "officer hand, official device and rider pixel visibility",
                               "failure_condition": "primary camera geometry cannot show the instruction and device response"},
                      changed_knobs=["camera_policy: standard to elevated"])
    return result


def build():
    entries = []
    for suffix in ("a", "b"):
        case = AID + "__probe_" + suffix
        primary = candidate(suffix, "primary")
        fallback = [candidate(suffix, name) for name in ("fallback1", "fallback2")]
        negative = primary["compatibility"]["negative_log"]
        saved, saved_hash = reference(f"selected-proofs/probe_{suffix}-primary-saved-processing.json")
        physical, physical_hash = reference(f"physical/probe-{suffix}/preparation-proof.json")
        entry = {"case_id": case, "kind": "delivery",
                 "construction": primary["construction"],
                 "construction_sha256": primary["construction_sha256"],
                 "candidate_risk": {"status": "physical",
                                    "reason": "Original rider response, officer direction and device/pixel visibility need review"},
                 "candidates": fallback,
                 "offline": primary["offline"],
                 "compatibility": primary["compatibility"],
                 "negative": {"log": negative},
                 "measurement_contract": f"native/officer/selected-contracts/probe_{suffix}-primary.json",
                 "measurement_procedure": {"entrypoint": "finalize.py",
                                           "output_schema": "c10365-selected-source-analysis-v1"},
                 "acquisition": {"kin.speed": {"entrypoint": "capture.py",
                                                "method": "sample original Native rider velocity for every joined frame",
                                                "evidence": "native-raw-actors.jsonl joined to capture/evidence.jsonl"}},
                 "fixture_recipe": primary["fixture_recipe"],
                 "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                 "physical_preparation": {"receipt": physical, "sha256": physical_hash},
                 "delivery_acceptance": {
                     "case_id": case, "sets": ["full-train"],
                     "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                                "actual_pixels", "physical_completion"],
                     "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
                     "command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case} --self-test",
                     "test_exit_code": 0, "test_log": f"audits/probe-{suffix}/positive.log",
                     "test_log_sha256": sha(HERE / f"audits/probe-{suffix}/positive.log"),
                     "negative_command": f".venv-cpu/bin/python work/{AID}/delivery_audit.py --case {case} --self-test --negative",
                     "negative_exit_code": 1,
                     "negative_expected_error": "Missing original source: exact original Native result",
                     "negative_log": f"audits/probe-{suffix}/negative.log",
                     "negative_log_sha256": sha(HERE / f"audits/probe-{suffix}/negative.log")},
                 "post_capture": {"command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT",
                                  "feedback_command": f"cat $OUTPUT/versions/*/feedback.json # {case}",
                                  "recorded_only": True, "test_exit_code": 0,
                                  "test_log": saved, "test_log_sha256": saved_hash}}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "selected_delivery_cpu_prepared", "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
