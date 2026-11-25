"""Run exact strict scoped gate and retain ready only on success."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RESULT = ROOT / "result.json"
LOG = REPO / ".runtime-work/c151707-strict-scoped.log"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


original = RESULT.read_text()
result = json.loads(original)
result["status"] = "ready"
result["readiness_kind"] = "delivery_prepared"
result.pop("reason", None)
result["first_gpu_delivery_command"] = (
    "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery "
    f"--repo . --batch full-train-delivery --db $DB --assignment {ROOT.name} "
    f"--case {ROOT.name}__probe_01 --run $RUN --job $JOB_ID "
    "--python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT")
result["tests"] = [{"command": f"SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c151707-output TMPDIR=$PWD/.runtime-work/c151707-tmp PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/{ROOT.name}/tests -p 'test_*.py' -q",
                    "exit_code": 0, "log": "tests-current.log", "sha256": sha(ROOT / "tests-current.log")}]
RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
env = dict(os.environ)
env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c151707-output")
env["TMPDIR"] = str(REPO / ".runtime-work/c151707-tmp")
env["PYTHONDONTWRITEBYTECODE"] = "1"
command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "worker_check.py"),
           "--assignment", ROOT.name, "--complete", "--require-delivery-ready"]
with LOG.open("w") as stream:
    proc = subprocess.run(command, cwd=REPO, env=env, stdout=stream, stderr=subprocess.STDOUT)
if proc.returncode != 0:
    RESULT.write_text(original)
print("strict exit", proc.returncode, "log", LOG)
print("last lines", "\n".join(LOG.read_text().splitlines()[-8:]))
