"""Pin synthetic positive, incomplete, missing, and lifecycle CPU proofs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c125745-250-2/physical"
PYTHON = REPO / ".venv-cpu/bin/python"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(args: list[str], log: Path, env: dict) -> None:
    done = subprocess.run(args, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout.rstrip() + "\n")
    if done.returncode:
        raise ValueError("proof failed: " + done.stdout[-1500:])


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    (SCRATCH / "output").mkdir(exist_ok=True)
    lifecycle_events = ["capture_finished", "encoders_closed", "restoration_verified",
                        "native_exit", "owner_released", "saved_processing_started"]
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        source = json.loads((ROOT / ("diagnostic-" + suffix + ".json")).read_text())
        positive = json.loads(source["files"]["original-attempt/entry-timing-source.json"])
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            packet = json.loads(json.dumps(positive))
            if kind == "incomplete_motion":
                for row in packet["frames"]:
                    row["other"]["body_corners_xy_m"] = [[-3, 4], [-2, 4], [-2, 5], [-3, 5]]
            elif kind == "missing_evidence":
                packet.pop("frames")
            fixture = SCRATCH / (suffix + "-" + kind + ".json")
            dump(fixture, packet)
            result = ROOT / ("cpu-physical-" + suffix + "-" + kind + ".json")
            log = ROOT / ("cpu-physical-" + suffix + "-" + kind + ".log")
            args = [str(PYTHON), str(ROOT / "physical_probe.py"), "--case", case,
                    "--fixture", str(fixture), "--result", str(result)]
            run(args, log, env)
            fixtures.append({"kind": kind, "command": " ".join(args), "exit_code": 0,
                             "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        life_fixture = SCRATCH / (suffix + "-lifecycle.json")
        dump(life_fixture, lifecycle_events)
        life_log = ROOT / ("cpu-lifecycle-" + suffix + ".log")
        args = [str(PYTHON), str(ROOT / "lifecycle_check.py"), "--events", str(life_fixture)]
        run(args, life_log, env)
        receipt = ROOT / ("cpu-physical-" + suffix + ".json")
        dump(receipt, {"case_id": case, "construction_sha256": entry["construction_sha256"],
                       "fixtures": fixtures,
                       "lifecycle": {"events": lifecycle_events, "exit_code": 0,
                                     "command": " ".join(args), "log": life_log.name,
                                     "log_sha256": sha(life_log)}})
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print(suffix + " physical and lifecycle passed", flush=True)
    dump(manifest_path, manifest)


if __name__ == "__main__":
    main()
