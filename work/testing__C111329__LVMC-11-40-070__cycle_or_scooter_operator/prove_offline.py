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
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
    else:
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    manifest["runtime_manifest_sha256"] = sha(REPO / "runtime/SOURCE-MANIFEST.json")
    manifest["status"] = "partial_cpu_preparation"
    dump(MANIFEST, manifest)
    scratch = REPO / ".runtime-work/c111329-offline-selected"
    scratch.mkdir(parents=True, exist_ok=True)
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        destination = scratch / suffix
        if destination.exists():
            import shutil
            shutil.rmtree(destination)
        command = [sys.executable, "runtime.py", "offline", "--manifest",
                   str(MANIFEST.relative_to(REPO)), "--case", entry["case_id"],
                   "--output", str(destination.relative_to(REPO)), "--python", sys.executable]
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c111329-output")
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        log = ROOT / f"cpu-offline-{suffix}.log"
        output = (result.stdout + result.stderr).rstrip() + "\n"
        log.write_text(output)
        if result.returncode:
            raise RuntimeError(f"offline failed for {suffix}: {output[-1000:]}")
        entry["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest " +
                       str(MANIFEST.relative_to(REPO)) + " --case " + entry["case_id"] +
                       " --output " + str(destination.relative_to(REPO)) +
                       " --python $PWD/.venv-cpu/bin/python",
            "exit_code": 0, "log": log.name, "log_sha256": sha(log),
            "construction_sha256": entry["construction_sha256"],
        }
        dump(MANIFEST, manifest)
        print("passed", suffix)


if __name__ == "__main__":
    main()
