"""Refresh truthful rail return metadata from current exact CPU receipts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
NATIVE = WORK / "native"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = WORK / "result.json"
    result = json.loads(path.read_text())
    manifest = json.loads((WORK / "execution-manifest.json").read_text())
    plan = json.loads((WORK / "case-plan.json").read_text())
    unit_names = ("rail_sight", "rail_scene", "rail_native_rays", "source_review",
                  "rail_join", "frame_capture", "runner", "controller", "finalize",
                  "comparison_audit")
    tests = []

    def add(command, log):
        source = WORK / log
        if not source.is_file():
            return
        tests.append({"command": command, "exit_code": 0,
                      "log": str(source.relative_to(WORK)), "sha256": sha(source)})

    for name in unit_names:
        add(".venv-cpu/bin/python -B work/" + WORK.name + "/native/prove_" + name + ".py",
            "native/" + name.replace("_", "-") + "-proof.log")
    add(".venv-cpu/bin/python -B work/" + WORK.name + "/tests/test_rail_contract.py",
        "tests/rail-contract-proof.log")
    offline = compatibility = physical = saved = delivery = 0
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate in (entry, *entry.get("candidates", [])):
            proof = candidate.get("offline")
            if proof:
                offline += 1
                add(proof["command"], proof["log"])
            receipt = candidate.get("compatibility")
            if receipt:
                compatibility += 1
                add("runtime.py compatibility --manifest work/" + WORK.name +
                    "/execution-manifest.json --case " + entry["case_id"] +
                    " --candidate " + ("primary" if candidate is entry else candidate["id"]),
                    receipt["log"])
        if entry.get("physical_preparation"):
            physical += 1
        if entry.get("post_capture"):
            saved += 1
            add(entry["post_capture"]["command"], entry["post_capture"]["test_log"])
        if entry.get("delivery_acceptance"):
            delivery += 1
            add(entry["delivery_acceptance"]["command"], entry["delivery_acceptance"]["test_log"])
    result["tests"] = tests
    result["counts"].update(selected_comparison_cases_planned=len(plan["cases"]),
                            comparisons_planned=len(plan["comparisons"]),
                            delivery_cases_prepared=delivery,
                            candidates_proven=compatibility,
                            offline_candidates_passed=offline,
                            physical_case_proofs_passed=physical,
                            saved_only_case_proofs_passed=saved)
    result["reason"] = ("Ten exact rail cases and nine source-isolated comparisons cover 15 mph below/at/above, "
                        "two-direction rail sight, flagman duty and signal alternatives. "
                        "Canonical semantic proposals and selected offline/public compatibility proofs are source bound. "
                        "CPU diagnostics do not claim actual CARLA execution, physical railway qualification or legal acceptance. "
                        "Assignment remains partial until exact strict delivery gate passes.")
    result["first_gpu_delivery_command"] = (
        "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange "
        "execute-delivery --repo . --batch full-train-delivery --db $DB --assignment " + WORK.name +
        " --case " + manifest["cases"][0]["case_id"] +
        " --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT")
    result["native_checkpoint"]["source_modules"] = {
        str(source.relative_to(NATIVE)): sha(source)
        for source in sorted(NATIVE.glob("*.py"))}
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "cases": len(manifest["cases"]),
                      "offline": offline, "compatibility": compatibility,
                      "physical": physical, "saved": saved, "delivery": delivery,
                      "tests": len(tests)}))


if __name__ == "__main__":
    main()
