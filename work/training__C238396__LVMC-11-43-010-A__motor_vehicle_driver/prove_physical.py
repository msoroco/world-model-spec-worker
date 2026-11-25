"""Run CPU physical outcome and lifecycle fixtures for selected cases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "physical_fixture.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c238396-output"),
               TMPDIR=str(ROOT / ".runtime-work"))
    for condition in ("probe_a", "probe_b"):
        directory = HERE / "proofs/physical" / condition
        directory.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = directory / (kind + ".json")
            log = directory / (kind + ".log")
            command = [sys.executable, str(SCRIPT), "--condition", condition,
                       "--kind", kind, "--output", str(result)]
            with log.open("w") as stream:
                proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                      stderr=subprocess.STDOUT, check=False)
            if proc.returncode:
                raise RuntimeError(f"{condition} {kind} failed: {log}")
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "log": str(log.relative_to(HERE)),
                             "log_sha256": sha(log), "result": str(result.relative_to(HERE)),
                             "result_sha256": sha(result)})
        result = directory / "lifecycle.json"
        log = directory / "lifecycle.log"
        command = [sys.executable, str(SCRIPT), "--condition", condition,
                   "--kind", "lifecycle", "--output", str(result)]
        with log.open("w") as stream:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                  stderr=subprocess.STDOUT, check=False)
        if proc.returncode:
            raise RuntimeError(f"{condition} lifecycle failed: {log}")
        life = json.loads(result.read_text())
        construction = HERE / "native" / condition / "construction.json"
        receipt = {"format": "c238396-physical-preparation-v1",
                   "case_id": "training__C238396__LVMC-11-43-010-A__motor_vehicle_driver__" + condition,
                   "construction_sha256": sha(construction), "fixtures": fixtures,
                   "lifecycle": {"events": life["events"], "command": " ".join(command),
                                 "exit_code": 0, "log": str(log.relative_to(HERE)),
                                 "log_sha256": sha(log)},
                   "original_native_executed": False,
                   "physical_completion_claimed": False}
        path = directory / "proof.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(condition, sha(path))


if __name__ == "__main__":
    main()
