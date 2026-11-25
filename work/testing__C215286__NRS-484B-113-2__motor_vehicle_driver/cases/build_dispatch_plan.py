"""Build exact local dispatch intent from the selected six-case manifest."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
AID = HERE.name
BASE = f"work/{AID}"
PREFIX = "PYTHONPATH=runtime/scenario_pipeline $CARLA_PYTHON -m worker_exchange"
COMMON = f"--repo . --batch batch.json --db $DB --assignment {AID}"


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if manifest["assignment_id"] != AID or [row["case_id"] for row in manifest["cases"]] != [
            row["case_id"] for row in plan["cases"]]:
        raise ValueError("Selected case inventory differs")
    rows = []
    for order, entry in enumerate(manifest["cases"], 1):
        case = entry["case_id"]
        primary = f"{PREFIX} prepare-delivery {COMMON} --case {case}"
        alternative = not case.endswith(("reverse_over_crosswalk", "reverse_stops_before_crosswalk"))
        audit_script = "reverse_alternative_delivery_audit.py" if alternative else "reverse_crosswalk_native_audit.py"
        rows.append({
            "order": order, "assignment_id": AID, "case_id": case,
            "prepare_command": primary,
            "execute_command": f"C215286_REVIEW_BUNDLE=$REVIEW_BUNDLE {PREFIX} execute-delivery {COMMON} --case {case} --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT",
            "accept_command": f"{PREFIX} accept-delivery {COMMON} --case {case} --run $RUN --job $JOB_ID --attempt $ATTEMPT --audit $AUDIT --review-archive /external/archive",
            "capture_command": f"C215286_REVIEW_BUNDLE=$REVIEW_BUNDLE $CARLA_PYTHON runtime.py capture --manifest {BASE}/execution-manifest.json --case {case} --output $ATTEMPT --host $CARLA_HOST --port $CARLA_PORT --python $CARLA_PYTHON",
            "postprocessing_command": f".venv-cpu/bin/python runtime.py process-saved --manifest {BASE}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR --owner-release-receipt $ATTEMPT/owner-release.json",
            "owner_release_command": f"SCENARIO_CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt $ATTEMPT --receipt $ATTEMPT/owner-release.json --acknowledge-owner-released",
            "additional_source_audit_command": f"SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-native-audit .venv-cpu/bin/python {BASE}/{audit_script} " + (f"--native $ANALYSIS {case} $ATTEMPT/owner-release.json" if alternative else f"$ANALYSIS {case} $ATTEMPT/owner-release.json"),
            "candidate_commands": {item["id"]: primary + " --candidate " + item["id"] for item in entry.get("candidates", [])},
        })
    commands = []
    for comparison in plan["comparisons"]:
        cid = comparison["comparison_id"]
        if cid == "reverse_crosswalk_boundary":
            command = f".venv-cpu/bin/python {BASE}/crosswalk_comparison_cli.py --positive $POSITIVE_ANALYSIS --stop-before $STOP_ANALYSIS --output $AUDIT"
        else:
            alternative = "intersection" if "intersection" in cid else "street_corner"
            command = f".venv-cpu/bin/python {BASE}/reverse_alternative_comparison.py --positive $POSITIVE_ANALYSIS --stop-before $STOP_ANALYSIS --alternative {alternative} --output $AUDIT"
        commands.append({"assignment_id": AID, "comparison_id": cid, "command": command})
    return {"format": "worker-assignment-dispatch-plan", "assignment_id": AID,
            "status": "partial_cpu_prepared", "cases": rows,
            "comparison_audit_commands": commands,
            "scope": "Exact local commands; Native site review and physical acceptance remain pending"}


if __name__ == "__main__":
    (HERE / "dispatch-plan.json").write_text(json.dumps(build(), indent=2) + "\n")
