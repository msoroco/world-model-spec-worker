"""Pin complete, incomplete, missing-source and lifecycle CPU fixtures."""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c135087-physical-v2"
PYTHON = str(REPO / ".venv-cpu/bin/python")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(args, log, env):
    done = subprocess.run(args, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout.rstrip() + "\n")
    if done.returncode:
        raise ValueError("proof failed: " + done.stdout[-1500:])


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    output = SCRATCH / "output"
    output.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(output))
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        source = json.loads((ROOT / ("diagnostic-" + suffix + ".json")).read_text())
        packet = json.loads(source["files"]["original-attempt/site-packet.json"])
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            item = json.loads(json.dumps(packet))
            if kind == "incomplete_motion":
                for row in item["rows"]:
                    row["entrant_parking_task_active"] = False
            elif kind == "missing_evidence":
                item.pop("rows")
            fixture = SCRATCH / (suffix + "-" + kind + ".json")
            dump(fixture, item)
            result = ROOT / ("cpu-physical-" + suffix + "-" + kind + ".json")
            log = ROOT / ("cpu-physical-" + suffix + "-" + kind + ".log")
            args = [PYTHON, str(ROOT / "physical_probe.py"), "--case", case,
                    "--fixture", str(fixture), "--result", str(result)]
            run(args, log, env)
            fixtures.append({"kind": kind, "command": " ".join(args), "exit_code": 0,
                             "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        life_fixture = SCRATCH / (suffix + "-lifecycle.json")
        dump(life_fixture, events)
        life_log = ROOT / ("cpu-lifecycle-" + suffix + ".log")
        args = [PYTHON, str(ROOT / "lifecycle_check.py"), "--events", str(life_fixture)]
        run(args, life_log, env)
        receipt = ROOT / ("cpu-physical-" + suffix + ".json")
        dump(receipt, {"case_id": case, "construction_sha256": entry["construction_sha256"],
                       "fixtures": fixtures,
                       "lifecycle": {"events": events, "exit_code": 0,
                                     "command": " ".join(args), "log": life_log.name,
                                     "log_sha256": sha(life_log)}})
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print(suffix + " physical and lifecycle proof passed", flush=True)
    dump(manifest_path, manifest)


if __name__ == "__main__":
    main()
