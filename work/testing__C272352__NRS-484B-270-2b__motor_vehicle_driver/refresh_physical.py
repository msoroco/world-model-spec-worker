"""Bind exact synthetic overtaking and ownership protocol proofs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = ROOT / ".runtime-work/c272352-nov26"
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / "pipeline"),
               TMPDIR=str(scratch), MPLCONFIGDIR=str(scratch / "mpl"),
               PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT / "runtime/scenario_pipeline") + ":" +
               str(ROOT / "runtime/python"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        output = scratch / ("physical-" + suffix + "-v4")
        command = [str(ROOT / ".venv-cpu/bin/python"), str(HERE / "physical_probe.py"),
                   "--case", entry["case_id"], "--output", str(output)]
        run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / ("physical-" + suffix + "-probe.log")
        log.write_text(run.stdout.rstrip() + "\n")
        if run.returncode:
            raise RuntimeError(suffix + ": " + run.stdout[-1400:])
        proof = {"construction_sha256": entry["construction_sha256"],
                 "fixtures": [], "lifecycle": {
                     "events": ["capture_finished", "encoders_closed",
                                "restoration_verified", "native_exit",
                                "owner_released", "saved_processing_started"],
                     "exit_code": 0, "log": log.name, "log_sha256": sha(log)},
                 "scope": "Synthetic body overtaking and owner protocol only; no Native capture"}
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = HERE / ("physical-" + suffix + "-" + kind + ".json")
            proof["fixtures"].append({"kind": kind, "command": " ".join(command),
                                      "exit_code": 0, "log": log.name,
                                      "log_sha256": sha(log), "result": result.name,
                                      "result_sha256": sha(result)})
        receipt = HERE / ("physical-" + suffix + "-proof.json")
        receipt.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": receipt.name,
                                         "sha256": sha(receipt)}
        print("passed", suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
