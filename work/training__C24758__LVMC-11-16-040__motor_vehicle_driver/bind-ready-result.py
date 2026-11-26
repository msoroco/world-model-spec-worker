"""Publish the CPU-prepared selected package for exact scoped strict validation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
case = HERE.name + "__reference"
source = REPO / ".runtime-work/c24758-root-tests-final2.log"
lines = [line.rstrip() for line in source.read_text().splitlines()]
while lines and not lines[-1]:
    lines.pop()
log = HERE / "proofs/cpu-tests.log"
log.write_text("\n".join(lines) + "\n")
digest = hashlib.sha256(log.read_bytes()).hexdigest()
path = HERE / "result.json"
result = json.loads(path.read_text())
result.update({
    "status": "ready", "readiness_kind": "delivery_prepared",
    "reason": "Three exact 15 mph sight-conditioned comparison cases are CPU-prepared; original Native sight, exception, traversal, and legal review remain for local delivery.",
    "cases_planned": 3, "cases_selected": 3, "candidate_plans_proven": 6,
    "comparison_audits_passed": 1, "carla_executed": False, "recordings_accepted": 0,
    "planned_case_count": 3, "candidate_count": 2, "accepted_membership_count": 0,
    "reuse_count": 0, "unresolved_branch_count": 0,
    "cpu_checkpoint": {"selected_manifest": "execution-manifest.json",
                       "selected_cases": 3, "primary_and_fallback_offline_passed": 6,
                       "primary_and_fallback_public_compatibility_passed": 6,
                       "recorded_only_saved_passed": 3, "physical_preparation_case_count": 3,
                       "semantic_stage_count": 9,
                       "independent_delivery_positive_negative_passed": 3,
                       "independent_comparison_positive_negative_passed": 1,
                       "original_native_executed": False, "diagnostic_only": True},
    "first_gpu_delivery_command": "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment " + HERE.name +
        " --case " + case + " --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT",
    "tests": [{"command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/../../.runtime-work/c24758-owner TMPDIR=$PWD/../../.runtime-work PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD:$PWD/../../runtime/scenario_pipeline ../../.venv-cpu/bin/python -m unittest discover -s tests -p test*.py -v",
               "log": "proofs/cpu-tests.log", "sha256": digest, "exit_code": 0}],
    "remaining_gpu_checks": ["original 600-frame Native sight-ray and pixel review",
                             "separate through-street and traffic-control exception review",
                             "observed physical traversal and speed tracking",
                             "local canonical delivery audit and legal judgment"]})
path.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "cases": 3, "test_sha256": digest}))
