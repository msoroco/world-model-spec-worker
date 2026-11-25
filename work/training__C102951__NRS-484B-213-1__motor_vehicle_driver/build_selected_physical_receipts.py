"""Run three synthetic physical outcomes and lifecycle for each selected case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    if ".runtime-work" not in Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().parts:
        raise ValueError("Set scratch output root under .runtime-work")
    for distance in (70, 120, 170):
        case_id = HERE.name + "__" + str(distance)
        source = HERE / f"selected-{distance}-primary-construction.json"
        dest = HERE / "physical-preparation" / str(distance)
        dest.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in (*KINDS, "lifecycle"):
            command = f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/{HERE.name}/prove_selected_physical.py --distance {distance} --kind {kind}"
            log = dest / (kind + ".log")
            with log.open("w") as stream:
                completed = subprocess.run([sys.executable, str(HERE / "prove_selected_physical.py"), "--distance", str(distance), "--kind", kind], env=os.environ.copy(), stdout=stream, stderr=subprocess.STDOUT, check=False)
            if completed.returncode:
                raise ValueError(f"{kind} {distance} exited {completed.returncode}: {log.read_text()}")
            if kind == "lifecycle":
                lifecycle = {"events": EVENTS, "exit_code": 0, "log": str(log.relative_to(HERE)), "log_sha256": sha(log), "scope": "synthetic closure-order test; no Native capture claimed"}
            else:
                result = dest / (kind + "-result.json")
                fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                                 "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                                 "result": str(result.relative_to(HERE)), "result_sha256": sha(result)})
        receipt = {"format": "worker-physical-preparation", "case_id": case_id,
                   "construction_sha256": sha(source), "fixtures": fixtures, "lifecycle": lifecycle}
        path = dest / "receipt.json"
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(distance, sha(path))


if __name__ == "__main__":
    run()
