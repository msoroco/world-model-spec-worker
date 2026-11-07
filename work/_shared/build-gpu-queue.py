"""Build deterministic, nondispatchable intent rows for every planned full-train case."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "work/_shared/gpu-queue.json"


def build(root=ROOT):
    batch = json.loads((root / "batch.json").read_text())
    rows = []
    comparisons = []
    for aid in sorted(batch["assignments"]):
        result = json.loads((root / "work" / aid / "result.json").read_text())
        if (result.get("status") != "blocked" or result.get("selected_case_count", 0) != 0):
            raise ValueError("Blocked queue would hide a selected or ready case: " + aid)
        plan = json.loads((root / "work" / aid / "case-plan.json").read_text())
        case_ids = [case["case_id"] for case in plan["cases"]]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Duplicate planned case: " + aid)
        manifest = "work/" + aid + "/execution-manifest.json"
        for case_id in sorted(case_ids):
            prefix = "PYTHONPATH=runtime/pipeline/scenario_pipeline python3.11 -m worker_exchange"
            identity = "--assignment " + aid + " --case " + case_id
            row = {
                "order": len(rows) + 1,
                "assignment_id": aid,
                "case_id": case_id,
                "status": "blocked",
                "dispatchable": False,
                "capture_command": "python3.11 runtime.py capture --manifest " + manifest
                    + " --case " + case_id + " --output ${ATTEMPT_DIR} --host ${CARLA_HOST}"
                    + " --port ${CARLA_PORT} --python ${NATIVE_PYTHON}",
                "postprocessing_command": "python3.11 runtime.py process-saved --manifest "
                    + manifest + " --case " + case_id + " --attempt ${ATTEMPT_DIR}"
                    + " --output ${PROCESSED_DIR} --library ${DECODER_LIBRARY}"
                    + " --validator ${VALIDATOR}",
                "owner_release_command": "CASE_ID=" + case_id
                    + " python3.11 runtime.py owner-released --attempt "
                    + "${ATTEMPT_DIR} --receipt ${OWNER_RELEASE_RECEIPT}"
                    + " --acknowledge-owner-released",
                "additional_source_audit_command": "CASE_ID=" + case_id
                    + " python3.11 worker_check.py --complete --require-delivery-ready",
                "prepare_command": prefix + " prepare-delivery --repo . --batch full-train-delivery"
                    + " --db ${WORKER_DB} " + identity,
                "execute_command": prefix + " execute-delivery --repo . --batch full-train-delivery"
                    + " --db ${WORKER_DB} --run ${RUN_ID} " + identity
                    + " --job ${JOB_ID} --python ${NATIVE_PYTHON} --host ${CARLA_HOST}"
                    + " --port ${CARLA_PORT}",
                "accept_command": prefix + " accept-delivery --repo . --batch full-train-delivery"
                    + " --db ${WORKER_DB} --run ${RUN_ID} " + identity
                    + " --job ${JOB_ID} --attempt ${ATTEMPT_ID} --audit ${ACCEPTANCE_AUDIT}",
                "candidate_commands": {
                    candidate: "python3.11 work/_shared/prepare-delivery-candidate.py "
                        + case_id + " " + candidate
                    for candidate in ("fallback1", "fallback2", "fallback3")
                },
            }
            rows.append(row)
        for item in sorted(plan["comparisons"], key=lambda c: c["comparison_id"]):
            comparisons.append({
                "assignment_id": aid,
                "comparison_id": item["comparison_id"],
                "status": "blocked",
                "dispatchable": False,
                "command": "python3.11 work/_shared/audit-gpu-queue.py --comparison "
                    + item["comparison_id"],
            })
    return {
        "format": "worker-ordered-gpu-queue-v1",
        "batch_id": batch["batch_id"],
        "status": "blocked",
        "cases": rows,
        "comparison_audit_commands": comparisons,
        "reason": "All planned exact case IDs are ordered; none is selected or dispatchable."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build()
    if args.check:
        if json.loads(QUEUE.read_text()) != data:
            raise ValueError("Ordered queue differs from current case plans")
    else:
        QUEUE.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(json.dumps({"passed": True, "cases": len(data["cases"]),
                      "comparisons": len(data["comparison_audit_commands"]),
                      "dispatchable": sum(row["dispatchable"] for row in data["cases"])}))
