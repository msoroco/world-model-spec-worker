"""Build a non-dispatchable exact-case handoff fragment for local integration."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
BATCH = "full-train-delivery"
CLI = "PYTHONPATH=runtime/pipeline/scenario_pipeline python3.11 -m worker_exchange"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    if len(manifest["cases"]) != 2 or any("delivery_acceptance" not in x for x in manifest["cases"]):
        raise ValueError("Two acceptance-prepared exact cases required")
    rows = []
    for order, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        common = f"--repo . --batch {BATCH} --db $DB --assignment {AID} --case {case}"
        rows.append({
            "order": order, "assignment_id": AID, "case_id": case,
            "status": "cpu_prepared_partial", "dispatchable": False,
            "capture_command": f"$CARLA_PYTHON runtime.py capture --manifest work/{AID}/execution-manifest.json --case {case} --output $ATTEMPT_DIR --host $CARLA_HOST --port $CARLA_PORT --python $CARLA_PYTHON",
            "postprocessing_command": f"python3.11 runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt $ATTEMPT_DIR --output $PROCESSED_DIR --library $DECODER_LIBRARY --validator $VALIDATOR",
            "owner_release_command": f"CASE_ID={case} python3.11 runtime.py owner-released --attempt $ATTEMPT_DIR --receipt $OWNER_RELEASE_RECEIPT --acknowledge-owner-released",
            "additional_source_audit_command": f"CASE_ID={case} python3.11 worker_check.py --assignment {AID} --complete --require-delivery-ready",
            "prepare_command": f"{CLI} prepare-delivery {common}",
            "execute_command": f"{CLI} execute-delivery {common} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT",
            "accept_command": f"{CLI} accept-delivery {common} --run $RUN --job $JOB_ID --attempt $ATTEMPT_ID --audit $ACCEPTANCE_AUDIT",
            "candidate_commands": {candidate["id"]: f"{CLI} prepare-delivery {common} --candidate {candidate['id']}"
                                   for candidate in entry["candidates"]}})
    plan = json.loads((HERE / "case-plan.json").read_text())
    comparisons = []
    for item in plan["comparisons"]:
        ident = item["comparison_id"]
        script = "prove-comparison-audit.py"
        comparisons.append({"assignment_id": AID, "comparison_id": ident,
                            "status": "cpu_diagnostic_only",
                            "command": f"python3.11 work/{AID}/{script}",
                            "original_comparison_acceptance_pending": True})
    out = {"format": "worker-exact-delivery-queue-fragment", "assignment_id": AID,
           "execution_manifest_sha256": sha(path), "status": "cpu_prepared_partial",
           "dispatchable": False, "cases": rows,
           "comparison_audit_commands": comparisons,
           "original_native_and_pixel_checks_pending": True}
    target = HERE / "update026-selected-delivery-queue-fragment.json"
    target.write_text(json.dumps(out, indent=2) + "\n")
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["first_gpu_delivery_command"] = rows[0]["execute_command"]
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"exact_cases": len(rows), "comparison_commands": len(comparisons),
                      "fragment_sha256": sha(target), "dispatchable": False}))


if __name__ == "__main__":
    main()
