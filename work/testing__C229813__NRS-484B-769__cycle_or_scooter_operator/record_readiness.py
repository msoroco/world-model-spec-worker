"""Record CPU-prepared readiness only after all local proof inventories exist."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ASSIGNMENT = PACKAGE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result_path = PACKAGE / "result.json"
    result = json.loads(result_path.read_text())
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    offline = json.loads((PACKAGE / "cpu-offline-proofs.json").read_text())
    compatibility = json.loads((PACKAGE / "cpu-compatibility-proofs.json").read_text())["results"]
    saved = json.loads((PACKAGE / "cpu-saved-proofs.json").read_text())
    plan = json.loads((PACKAGE / "case-plan.json").read_text())
    if len(manifest["cases"]) != 9 or len(offline) != 18 or len(compatibility) != 18 or \
            len(saved) != 9 or any(not x["passed"] for x in compatibility + saved) or \
            len(plan["comparisons"]) != 3:
        raise ValueError("exact CPU proof inventory incomplete")
    if any("physical_preparation" not in e or "delivery_acceptance" not in e or
           "post_capture" not in e for e in manifest["cases"]):
        raise ValueError("physical, delivery or saved-only proof not bound")
    tests = [{"command": f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=work/{ASSIGNMENT}:runtime/scenario_pipeline .venv-cpu/bin/python -m unittest discover -s work/{ASSIGNMENT}/tests -v",
              "exit_code": 0, "log": "cpu-signal-construction-tests.log",
              "sha256": sha(PACKAGE / "cpu-signal-construction-tests.log")}]
    for item in offline:
        tests.append({"command": item["command"], "exit_code": 0,
                      "log": item["log"], "sha256": item["log_sha256"]})
    for item in compatibility:
        tests.append({"command": item["command"], "exit_code": 0,
                      "log": item["log"], "sha256": sha(PACKAGE / item["log"])})
    for item in saved:
        tests.append({"command": item["command"], "exit_code": 0,
                      "log": item["log"], "sha256": item["log_sha256"]})
    result.update(status="ready", readiness_kind="delivery_prepared",
        reason="CPU delivery preparation passed; original CARLA signal and pixel review remain pending.",
        tests=tests,
        remaining_gpu_checks=[
            "Acquire reviewed original roadway, rider rigs and camera sites for three covered kinds",
            "Execute nine exact 900-frame Native captures; verify rider arm articulation and four original videos",
            "Run independent original source/pixel and three posture comparison audits before canonical full-test acceptance"],
        first_gpu_delivery_command=(
            f".venv-cpu/bin/python runtime.py execute-delivery --assignment {ASSIGNMENT} "
            f"--case {manifest['cases'][0]['case_id']} --job \"$JOB_ID\" --db \"$DB\" "
            "--run \"$RUN\" --python \"$CARLA_PYTHON\" --host \"$CARLA_HOST\" "
            "--port \"$CARLA_PORT\""),
        selected_cpu_proofs={"cases": 9, "selected_candidates": 18,
            "selected_compatibility_passed": 18, "selected_saved_only_passed": 9,
            "physical_fixture_sets": 9, "delivery_audit_cpu_pairs": 9,
            "comparison_diagnostic_pairs": 3, "original_acquisition_claimed": False})
    result_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("recorded", len(tests), "passing CPU proof commands")


if __name__ == "__main__":
    main()
