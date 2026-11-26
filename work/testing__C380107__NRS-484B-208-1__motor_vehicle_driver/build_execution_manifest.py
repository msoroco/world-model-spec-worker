"""Bind current exact CPU proofs into source-gated delivery manifest."""

import hashlib
import json
from pathlib import Path

from package_contract import ASSIGNMENT

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((HERE / relative).read_text())


def main():
    source = read("diagnostic-execution-manifest.json")
    saved = {item["case_id"]: item for item in read("saved-proof-summary.json")["cases"]}
    post = {item["case_id"]: item for item in read("post-compat-proof-summary.json")["cases"]}
    if len(source["cases"]) != 18 or len(saved) != 18 or len(post) != 18:
        raise ValueError("all eighteen selected exact proofs required")
    proposal = read("proposals/cases.json")
    description = next(c["recording_description"] for c in proposal["cases"] if c.get("target_law_id"))
    acquisition = {channel["name"]: {
        "entrypoint": "native_adapter.py" if channel["name"] in (
            "ego_rear_lane_speed_gap", "four_synchronized_camera_views", "original_sign_exposure_s") else "analysis.py",
        "method": "source-gated original actor/camera readback and saved source-bound derivation",
        "evidence": "reviewed map/HOV authority, original 20 Hz Native trace and four-camera frame map"}
        for channel in description["channels"]}
    entries = []
    for initial in source["cases"]:
        entry = dict(initial)
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        folder = HERE / "cases" / suffix
        construction = HERE / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("stale exact construction: " + suffix)
        compatibility = folder / "compatibility.json"
        proof = json.loads(compatibility.read_text())
        if not proof.get("passed") or proof.get("construction_sha256") != entry["construction_sha256"]:
            raise ValueError("stale exact compatibility: " + suffix)
        entry["kind"] = "delivery"
        entry["status"] = "source_gated_cpu_preparation"
        entry["acquisition"] = acquisition
        entry["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + ASSIGNMENT +
                            "/execution-manifest.json --case " + case_id + " --output $OFFLINE",
                            "construction_sha256": entry["construction_sha256"], "exit_code": 0,
                            "log": "cases/" + suffix + "/offline.log",
                            "log_sha256": sha(folder / "offline.log")}
        entry["compatibility"] = {"receipt": "cases/" + suffix + "/compatibility.json",
                                  "sha256": sha(compatibility),
                                  "log": "cases/" + suffix + "/cpu-analysis.log"}
        entry["negative"] = {"log": "cases/" + suffix + "/negative-analysis.log"}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        physical = post[case_id]
        entry["physical_preparation"] = {"receipt": physical["physical_preparation"],
                                         "sha256": physical["physical_preparation_sha256"]}
        entry["pending_original_sources"] = [
            "reviewed original Nevada controlled-access highway, lane markings and posted-limit authority",
            "source-sealed HOV designation, hours, access, signs, occupancy and vehicle-category packets",
            "released Native 900-frame four-view ego/rear attempt and independent physical review"]
        entry["post_capture"] = {"recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + ASSIGNMENT +
                       "/execution-manifest.json --case " + case_id +
                       " --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR",
            "feedback_command": ".venv-cpu/bin/python work/" + ASSIGNMENT +
                                "/delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT --case " + case_id,
            "test_exit_code": 0, "test_log": saved[case_id]["log"],
            "test_log_sha256": saved[case_id]["log_sha256"]}
        positive, negative = physical["delivery_positive"], physical["delivery_negative"]
        entry["delivery_acceptance"] = {"case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(HERE / "delivery_audit.py"),
            "command": positive["command"], "test_exit_code": 0,
            "test_log": positive["log"], "test_log_sha256": positive["log_sha256"],
            "negative_command": negative["command"], "negative_exit_code": 1,
            "negative_expected_error": "released original highway/HOV Native attempt required",
            "negative_log": negative["log"], "negative_log_sha256": negative["log_sha256"],
            "diagnostic_fixture": True,
            "scope": "synthetic audit protocol CPU proof; original Native delivery pending"}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "status": "source_gated_cpu_preparation", "original_delivery_claimed": False,
                "runtime_manifest_sha256": source["runtime_manifest_sha256"], "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("Bound", len(entries), "exact selected CPU proof chains")


if __name__ == "__main__":
    main()
