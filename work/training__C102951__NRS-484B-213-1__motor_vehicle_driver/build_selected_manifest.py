"""Bind selected current-runtime proofs into an exact delivery draft."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bind_root():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "two-lane road, centerline, crest and all passing actors", "interval": "entire 30-second selected attempt"},
            {"view": "approach", "subject": "ego, overtaken and approaching vehicles", "interval": "entire 30-second selected attempt"},
            {"view": "reference_corner", "subject": "crest, centerline and full passing trajectory", "interval": "entire 30-second selected attempt"},
            {"view": "driver_reference", "subject": "driver-reference sightline, opposing lane and original pixels", "interval": "entire 30-second selected attempt"},
        ],
    }
    for case in plan["cases"]:
        case["selected"] = True
        case["planning_status"] = "selected_cpu_preparation; physical outcome unverified"
    write(plan_path, plan)
    construction = json.loads((HERE / "selected-120-primary-construction.json").read_text())
    construction["mechanisms"] = ["synchronous 20 Hz Native capture", "four-camera source recording", "left-of-center passing controller", "source-bound saved pass and separate vehicle-response measurement"]
    config_item = next(item for item in construction["files"] if item["path"] == "config.json")
    config = json.loads(config_item["content"])
    config["supported_case_ids"] = [ASSIGNMENT + "__" + str(d) for d in (70, 120, 170)]
    config["case_plan_sha256"] = sha(plan_path)
    config_item["content"] = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    plan_item = next(item for item in construction["files"] if item["path"] == "case-plan.json")
    plan_item["content"] = plan_path.read_text()
    for item in construction["files"]:
        target = HERE / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["path"] == "case-plan.json":
            continue
        target.write_text(item["content"])
    write(HERE / "construction.json", construction)


def proof(distance, candidate, key):
    suffix = f"{distance}-{candidate}"
    base = HERE / "selected-compatibility" / suffix
    if key == "compatibility":
        return {"receipt": str((base / "compatibility.json").relative_to(HERE)),
                "sha256": sha(base / "compatibility.json"),
                "log": str((base / "analysis.log").relative_to(HERE)),
                "negative_log": str((base / "negative.log").relative_to(HERE))}
    if key == "saved":
        base = HERE / "selected-saved" / suffix
        return {"receipt": str((base / "processing.json").relative_to(HERE)),
                "sha256": sha(base / "processing.json"), "recorded_only": True,
                "originals_preserved": True,
                "log": str((base / "analysis.log").relative_to(HERE)),
                "log_sha256": sha(base / "analysis.log")}
    raise ValueError(key)


def main():
    bind_root()
    draft = json.loads((HERE / "selected-draft-execution-manifest.json").read_text())
    offline = json.loads((HERE / "selected-offline-proof.json").read_text())
    by_offline = {(case["case_id"], case["candidate_id"]): case for case in offline["cases"]}
    script_sha = sha(HERE / "delivery_audit.py")
    entries = []
    for source in draft["cases"]:
        entry = deepcopy(source)
        case_id = entry["case_id"]
        distance = int(case_id.rsplit("__", 1)[-1])
        row = by_offline[(case_id, "primary")]
        offline_command = f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/selected-draft-execution-manifest.json --case {case_id} --candidate primary --output .runtime-work/c102951-current/offline-{distance}-primary --python $PWD/.venv-cpu/bin/python"
        entry["id"] = "primary"
        entry["offline"] = {"command": offline_command, "construction_sha256": entry["construction_sha256"], "exit_code": 0,
                            "log": row["offline_log"], "log_sha256": row["offline_log_sha256"]}
        entry["compatibility"] = proof(distance, "primary", "compatibility")
        entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
        entry["saved_processing"] = proof(distance, "primary", "saved")
        for candidate in entry["candidates"]:
            row = by_offline[(case_id, candidate["id"])]
            candidate["offline"] = {"command": offline_command.replace("primary", candidate["id"]),
                                    "construction_sha256": candidate["construction_sha256"], "exit_code": 0,
                                    "log": row["offline_log"], "log_sha256": row["offline_log_sha256"]}
            candidate["compatibility"] = proof(distance, candidate["id"], "compatibility")
            candidate["saved_processing"] = proof(distance, candidate["id"], "saved")
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"] if item["path"] == "config.json"))
        evidence = ["native-observed.jsonl", "trace.jsonl", "road-readback.json", "video_frames.jsonl", "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]
        entry["acquisition"] = {name: {"entrypoint": "finalize.py", "evidence": evidence,
                                        "method": "source-derived saved pass, response and original camera/frame audit"}
                                for name in set(config.get("required_atoms", [])) |
                                {channel["name"] for channel in construction["recording_description"]["channels"]}}
        physical = HERE / "physical-preparation" / str(distance) / "receipt.json"
        entry["physical_preparation"] = {"receipt": str(physical.relative_to(HERE)), "sha256": sha(physical)}
        command = f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case_id} --attempt $ATTEMPT --output $SAVED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $ATTEMPT/owner-release.json"
        saved_log = HERE / entry["saved_processing"]["log"]
        entry["post_capture"] = {"command": command, "feedback_command": command,
                                 "recorded_only": True, "scope": "Recorded-only synthetic fixture proof; original Native review pending",
                                 "test_exit_code": 0, "test_log": entry["saved_processing"]["log"],
                                 "test_log_sha256": sha(saved_log)}
        base = HERE / "delivery-acceptance" / str(distance)
        audit_cmd = f"PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --case {case_id} --selftest"
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["full-train"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": script_sha,
            "command": audit_cmd, "test_exit_code": 0,
            "test_log": str((base / "positive.log").relative_to(HERE)),
            "test_log_sha256": sha(base / "positive.log"),
            "negative_command": audit_cmd + " --negative-fixture", "negative_exit_code": 1,
            "negative_expected_error": "Synthetic fixture cannot establish original Native delivery",
            "negative_log": str((base / "negative.log").relative_to(HERE)),
            "negative_log_sha256": sha(base / "negative.log"),
        }
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
                "status": "selected_cpu_prepared_pending_strict", "delivery_ready": False,
                "original_native_observed": False, "cases": entries}
    write(HERE / "execution-manifest.json", manifest)
    print("manifest", sha(HERE / "execution-manifest.json"))


if __name__ == "__main__":
    main()
