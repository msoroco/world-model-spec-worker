"""Bind three source-bound physical outcomes and owner-release proof per case."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c412262-new"
MANIFEST = HERE / "execution-manifest.json"
PYTHON = str(REPO / ".venv-cpu/bin/python")
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    os.environ["TMPDIR"] = os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        fixtures = []
        life = None
        for kind in KINDS:
            result = HERE / f"physical-{tag}-{kind}.json"
            log = HERE / f"physical-{tag}-{kind}.log"
            command = [PYTHON, str(HERE / "physical_probe.py"),
                       "--case", entry["case_id"], "--kind", kind,
                       "--output", str(result)]
            if result.exists():
                result.unlink()
            run = subprocess.run(command, cwd=REPO, env=os.environ,
                                 capture_output=True, text=True, timeout=120)
            log.write_text((run.stdout + run.stderr).rstrip() + "\n")
            if run.returncode:
                raise RuntimeError(tag + " " + kind + ": " + log.read_text()[-2000:])
            outcome = json.loads(run.stdout)
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "log": log.name,
                             "log_sha256": sha(log), "result": result.name,
                             "result_sha256": sha(result)})
            if kind == "complete_motion":
                life = {"events": outcome["events"], "exit_code": 0,
                        "log": log.name, "log_sha256": sha(log)}
        receipt = HERE / f"physical-{tag}-receipt.json"
        write(receipt, {"case_id": entry["case_id"],
                        "construction_sha256": entry["construction_sha256"],
                        "fixtures": fixtures, "lifecycle": life})
        entry["physical_preparation"] = {"receipt": receipt.name,
                                          "sha256": sha(receipt)}
        MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        print(tag, "physical/lifecycle passed", flush=True)


if __name__ == "__main__":
    main()
