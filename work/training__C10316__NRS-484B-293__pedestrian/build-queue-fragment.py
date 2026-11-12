"""Build the selected C10316 rows for later canonical queue assembly.

This emits intent only. It does not dispatch, claim acceptance, or modify the
shared queue while the complete batch is still partial.
"""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
AID = HERE.name
PREFIX = "PYTHONPATH=runtime/pipeline/scenario_pipeline python3.11 -m worker_exchange"
MANIFEST = f"work/{AID}/execution-manifest.json"


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        identity = f"--assignment {AID} --case {case}"
        base = PREFIX + " --repo . --batch full-train-delivery --db ${WORKER_DB} " + identity
        candidates = {candidate["id"] for candidate in entry["candidates"]}
        if candidates != {"fallback1", "fallback2", "fallback3"}:
            raise ValueError("Selected C10316 fallback set changed: " + case)
        candidate_commands = {
            candidate: (PREFIX + " prepare-delivery --repo . --batch full-train-delivery"
                        + " --db ${WORKER_DB} " + identity + " --candidate " + candidate)
            for candidate in sorted(candidates | {"primary"})
        }
        rows.append({
            "assignment_id": AID, "case_id": case, "status": "partial",
            "dispatchable": False,
            "capture_command": "python3.11 runtime.py capture --manifest " + MANIFEST
                + " --case " + case + " --output ${ATTEMPT_DIR} --host ${CARLA_HOST}"
                + " --port ${CARLA_PORT} --python ${NATIVE_PYTHON}",
            "postprocessing_command": "python3.11 runtime.py process-saved --manifest "
                + MANIFEST + " --case " + case + " --attempt ${ATTEMPT_DIR}"
                + " --output ${PROCESSED_DIR} --library ${DECODER_LIBRARY}"
                + " --validator ${VALIDATOR}",
            "owner_release_command": "CASE_ID=" + case
                + " python3.11 runtime.py owner-released --attempt ${ATTEMPT_DIR}"
                + " --receipt ${OWNER_RELEASE_RECEIPT} --acknowledge-owner-released",
            "additional_source_audit_command": "python3.11 work/" + AID
                + "/physical_outcome_audit.py --attempt ${ATTEMPT_DIR} --case " + case,
            "prepare_command": base.replace(" -m worker_exchange ",
                                             " -m worker_exchange prepare-delivery "),
            "execute_command": base.replace(" -m worker_exchange ",
                                             " -m worker_exchange execute-delivery ")
                + " --run ${RUN_ID} --job ${JOB_ID} --python ${NATIVE_PYTHON}"
                + " --host ${CARLA_HOST} --port ${CARLA_PORT}",
            "accept_command": base.replace(" -m worker_exchange ",
                                            " -m worker_exchange accept-delivery ")
                + " --run ${RUN_ID} --job ${JOB_ID} --attempt ${ATTEMPT_ID}"
                + " --audit ${ACCEPTANCE_AUDIT}",
            "candidate_commands": candidate_commands,
        })
    comparisons = [{"assignment_id": AID,
                    "comparison_id": item["comparison_id"],
                    "status": "partial", "dispatchable": False,
                    "command": "COMPARISON_ID=" + item["comparison_id"]
                        + " python3.11 work/" + AID
                        + "/comparison_audit.py --reference-audit ${REFERENCE_AUDIT}"
                        + " --contrast-audit ${CONTRAST_AUDIT} --output ${COMPARISON_AUDIT}"}
                   for item in plan["comparisons"]]
    return {"format": "c10316-selected-queue-fragment-v1",
            "manifest_status": manifest["status"],
            "cases": rows, "comparison_audit_commands": comparisons,
            "dispatchable": False}


if __name__ == "__main__":
    fragment = build()
    output = HERE / "update023-selected-queue-fragment.json"
    output.write_text(json.dumps(fragment, indent=2) + "\n")
    print(json.dumps({"cases": len(fragment["cases"]),
                      "comparisons": len(fragment["comparison_audit_commands"]),
                      "candidates": sum(len(row["candidate_commands"])
                                        for row in fragment["cases"]),
                      "dispatchable": fragment["dispatchable"]}))
