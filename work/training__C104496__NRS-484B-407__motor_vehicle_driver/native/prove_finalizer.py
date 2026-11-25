"""Exercise source-bound saved finalization on each C104496 diagnostic case."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SCRATCH = ROOT / ".runtime-work/c104496-finalizer-proof-v5"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def exercise(stage, expected_success=True):
    output = stage / "analysis-report.json"
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT / "runtime/scenario_pipeline"))
    run = subprocess.run([sys.executable, str(HERE / "finalize.py"),
                          "--attempt", str(stage), "--output", str(output)],
                         cwd=stage, env=env, capture_output=True, text=True,
                         timeout=90)
    if bool(run.returncode == 0) != expected_success:
        raise ValueError("finalizer outcome differs: " + run.stderr[-1000:])
    return run


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from batch_pipeline.carla import validate_attempt
    proposal = json.loads((CASE / "proposals/cases.json").read_text())
    reports = []
    for suffix, branch in (("probe_01", "crest"), ("probe_02", "crest"),
                           ("probe_03", "curve")):
        fixture = ROOT / ".runtime-work/c104496-fixture-proof-v3" / suffix
        if not fixture.is_dir():
            raise ValueError("materialized source fixture missing: " + suffix)
        stage = SCRATCH / suffix
        if stage.exists():
            raise ValueError("use fresh finalizer proof scratch")
        shutil.copytree(fixture, stage)
        config = json.loads((CASE / "native" / branch / "drafts" / suffix /
                             "primary/config.json").read_text())
        config["selected_case_id"] = CASE.name + "__" + suffix
        case = next(c for c in proposal["cases"] if c["case_id"] ==
                    config["selected_case_id"])
        construction = {"case_id": case["case_id"],
                        "recording_description": case["recording_description"]}
        write(stage / "config.json", config)
        write(stage / "construction.json", construction)
        positive = exercise(stage)
        result = json.loads((stage / "result.json").read_text())
        report = json.loads((stage / "analysis-report.json").read_text())
        if (result["case_id"] != case["case_id"] or result["setup_confirmed"] or
                result["maneuver_completed"] or result["accepted"] or
                len(result["recording_evidence"]) != 8 or
                len(report["measurements"]) != 4):
            raise ValueError("diagnostic finalizer overclaimed or omitted source")
        validated = validate_attempt(stage,
            {"case": case, "cell": {"cell_id": "C104496"},
             "actor": "motor_vehicle_driver"}, construction,
            {"recorded_exit_code": 0}, {})
        if not validated["rebuild_required"] or validated["case_id"] != case["case_id"]:
            raise ValueError("generic saved Native validation overstated acceptance")
        negative = SCRATCH / (suffix + "-missing-ray")
        shutil.copytree(fixture, negative)
        write(negative / "config.json", config)
        write(negative / "construction.json", construction)
        (negative / "analytic_sight.jsonl").unlink()
        failed = exercise(negative, False)
        if "Missing required source: analytic_sight.jsonl" not in failed.stderr:
            raise ValueError("missing case-specific sight source was not rejected")
        reports.append({"case_id": case["case_id"],
                        "finalizer_sha256": sha(HERE / "finalize.py"),
                        "analysis_sha256": sha(stage / "analysis-report.json"),
                        "result_sha256": sha(stage / "result.json"),
                        "negative_error": "Missing required source: analytic_sight.jsonl",
                        "generic_native_validation": True,
                        "synthetic_diagnostic": True, "physical_original_proven": False})
        print(json.dumps({"completed": suffix, "source_joins": 700}), flush=True)
    proof = {"format": "c104496-finalizer-source-proof-v1",
             "assignment_id": CASE.name, "cases": reports, "passed": True}
    path = CASE / "finalizer-source-proof.json"
    write(path, proof)
    print(json.dumps({"passed": True, "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
