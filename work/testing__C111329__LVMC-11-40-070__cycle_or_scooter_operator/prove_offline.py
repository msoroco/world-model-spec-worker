"""Run and bind each exact inline construction's CPU-only check."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    manifest["runtime_manifest_sha256"] = sha(REPO / "runtime/SOURCE-MANIFEST.json")
    manifest["status"] = "partial_cpu_preparation"
    dump(MANIFEST, manifest)
    scratch = REPO / ".runtime-work/c111329-offline-selected"
    scratch.mkdir(parents=True, exist_ok=True)
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate_id, selected in [("primary", entry)] + [(item["id"], item) for item in entry["candidates"]]:
            destination = scratch / suffix / candidate_id
            if destination.exists():
                import shutil
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "runtime.py", "offline", "--manifest",
                       str(MANIFEST.relative_to(REPO)), "--case", entry["case_id"],
                       "--output", str(destination.relative_to(REPO)), "--python", sys.executable]
            if candidate_id != "primary":
                command.extend(["--candidate", candidate_id])
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c111329-output")
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            log = ROOT / f"cpu-offline-{suffix}-{candidate_id}.log"
            output = (result.stdout + result.stderr).rstrip() + "\n"
            log.write_text(output)
            if result.returncode:
                raise RuntimeError(f"offline failed for {suffix}/{candidate_id}: {output[-1000:]}")
            command_text = ".venv-cpu/bin/python runtime.py offline --manifest " + \
                           str(MANIFEST.relative_to(REPO)) + " --case " + entry["case_id"] + \
                           " --output " + str(destination.relative_to(REPO)) + \
                           " --python $PWD/.venv-cpu/bin/python"
            if candidate_id != "primary":
                command_text += " --candidate " + candidate_id
            selected["offline"] = {"command": command_text, "exit_code": 0,
                                   "log": log.name, "log_sha256": sha(log),
                                   "construction_sha256": selected["construction_sha256"]}
            dump(MANIFEST, manifest)
            print("passed", suffix, candidate_id)


if __name__ == "__main__":
    main()
