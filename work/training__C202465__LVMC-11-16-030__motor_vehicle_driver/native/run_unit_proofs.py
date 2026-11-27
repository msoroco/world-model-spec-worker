"""Rerun rail source, controller, join and comparison CPU proofs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
NATIVE = WORK / "native"
RESULT = WORK / "result.json"
PROOFS = ("rail_sight", "rail_scene", "rail_native_rays", "source_review",
          "rail_join", "frame_capture", "runner", "controller", "finalize",
          "comparison_audit")


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".runtime-work"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c202465-unit-env"),
               PYTHONPATH=str(ROOT / "runtime/scenario_pipeline"))
    result = json.loads(RESULT.read_text())
    keep = [entry for entry in result.get("tests", [])
            if not any("/prove_" + name + ".py" in entry.get("command", "") for name in PROOFS)]
    for name in PROOFS:
        path = NATIVE / ("prove_" + name + ".py")
        log = NATIVE / (name.replace("_", "-") + "-proof.log")
        command = [str(ROOT / ".venv-cpu/bin/python"), "-B", str(path)]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        log.write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError("Failed " + name + ": " + log.read_text()[-2000:])
        digest = hashlib.sha256(log.read_bytes()).hexdigest()
        keep.append({"command": " ".join(command), "exit_code": 0,
                     "log": str(log.relative_to(ROOT)), "sha256": digest,
                     "scope": "synthetic CPU source and implementation proof; no physical acceptance"})
        print("PASS unit", name, flush=True)
    result["tests"] = keep
    RESULT.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
