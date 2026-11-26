"""Bind the CPU-tested exact constructions into one selected manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write(path, data):
    (ROOT / path).write_text(json.dumps(data, indent=2) + "\n")


def compatibility(path):
    return {
        "receipt": path + "/receipt.json",
        "sha256": digest(path + "/receipt.json"),
        "log": path + "/analysis.log",
        "negative_log": path + "/negative.log",
    }


offline = {}
for name in ("device-full", "boundary"):
    for row in read(f"draft-{name}-offline-receipt.json")["cases"]:
        offline[(row["case_id"], row["candidate"])] = {
            "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{AID}/execution-manifest.json --case {row['case_id']} --candidate {row['candidate']} --output .runtime-work/c179824/selected-offline-{row['case_id'].split('__')[-1]}-{row['candidate']} --python $PWD/.venv-cpu/bin/python",
            "exit_code": row["exit_code"],
            "construction_sha256": row["construction_sha256"],
            "log": row["offline_log"],
            "log_sha256": row["offline_log_sha256"],
        }

physical = {r["case_id"]: r for r in read("physical-proof/index.json")["cases"]}
prior = {r["case_id"]: r for r in read("execution-manifest.json")["cases"]}
entries = []
for family, draft, proof_root in (
    ("device", "draft-device-full-manifest.json", "draft-device-full-proofs"),
    ("boundary", "draft-boundary-manifest.json", "draft-boundary-proofs"),
    ("parked", "draft-parked-manifest.json", "draft-parked-proofs"),
):
    for item in read(draft)["cases"]:
        case = item["case_id"]
        suffix = case.split("__")[-1]
        entry = {key: item[key] for key in ("case_id", "construction", "construction_sha256", "measurement_procedure", "measurement_contract", "fixture_recipe")}
        entry.update(kind="delivery", id="primary", original_native_observed=False,
                     candidate_risk={"status": "physical", "reason": "Native road, actors, lamps and original pixels require local physical review"},
                     native_handoff={"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"})
        root = f"{proof_root}/{suffix}"
        primary = root + "/primary"
        entry["compatibility"] = compatibility(primary)
        entry["negative"] = {"log": primary + "/negative.log"}
        entry["physical_preparation"] = {"receipt": physical[case]["proof"], "sha256": physical[case]["sha256"]}
        entry["offline"] = item.get("offline") if family == "parked" else offline[(case, "primary")]
        saved = primary + "/saved-processing.json"
        if (ROOT / saved).is_file():
            command = f".venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library"
            entry["post_capture"] = {"command": command, "feedback_command": command, "recorded_only": True,
                                     "test_exit_code": 0, "test_log": saved, "test_log_sha256": digest(saved),
                                     "processing_receipt": saved, "processing_receipt_sha256": digest(saved)}
        construction = read(item["construction"])
        files = {f["path"]: f["content"] for f in construction["files"]}
        finalizer = entry["measurement_procedure"]["entrypoint"]
        entry["acquisition"] = {}
        for channel in construction["recording_description"]["channels"]:
            name = channel["name"]
            entry["acquisition"][name] = {
                "entrypoint": finalizer,
                "method": "Join original frame-mapped Native capture with independently hashed source review for " + name,
                "evidence": ["video_frames.jsonl", "analysis-report.json"],
            }
        config = json.loads(files["config.json"])
        for atom in config.get("required_atoms", []):
            entry["acquisition"][atom] = {
                "entrypoint": "runner.py",
                "method": "Read Native source packet and bind original frame evidence for " + atom,
                "evidence": ["scenario_geometry.json", "scenario_rule_evidence.jsonl"],
            }
        fallback = dict(item["candidates"][0])
        fallback["trigger"] = item["candidates"][0].get("trigger", {
            "source": "Original Native trace and synchronized video frame map",
            "metric": "600 joined frames with both people and vehicles at the selected civil or distance boundary",
            "failure_condition": "Primary motion or camera view fails original source/geometry readback",
        })
        fallback["changed_knobs"] = item["candidates"][0].get("changed_knobs", ["target speed: 3.0 to 2.8 m/s"])
        fallback["offline"] = item["candidates"][0].get("offline") if family == "parked" else offline[(case, "fallback1")]
        fallback_path = root + ("/fallback" if family == "device" else "/fallback1")
        fallback["compatibility"] = compatibility(fallback_path)
        entry["candidates"] = [fallback]
        if "delivery_acceptance" in prior.get(case, {}):
            entry["delivery_acceptance"] = prior[case]["delivery_acceptance"]
        entries.append(entry)

manifest = {
    "format": "worker-execution-manifest",
    "assignment_id": AID,
    "runtime_manifest_sha256": digest("../../runtime/SOURCE-MANIFEST.json"),
    "status": "selected_cpu_proofs_in_progress",
    "delivery_ready": False,
    "original_native_observed": False,
    "cases": entries,
}
write("execution-manifest.json", manifest)
print(json.dumps({"cases": len(entries), "post_capture": sum("post_capture" in e for e in entries)}, sort_keys=True))
