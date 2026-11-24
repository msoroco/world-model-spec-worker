"""Build a fresh exact-case compatibility fixture for CPU audit scripts."""

import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
PREFIX = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__"
MANIFEST = PACKAGE / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c158208-current-validator/.lake/build/bin/adapterCheck"


def ensure_validator():
    if VALIDATOR.is_file():
        return VALIDATOR
    library = VALIDATOR.parents[3]
    library.parent.mkdir(exist_ok=True)
    if not library.exists():
        shutil.copytree(ROOT / "runtime/library", library)
    result = subprocess.run(["lake", "build", "adapterCheck"], cwd=library,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode or not VALIDATOR.is_file():
        raise ValueError("Active-runtime Lean validator build failed\n" + result.stdout[-2000:])
    return VALIDATOR


def build(kind, output, manifest=MANIFEST):
    output = Path(output)
    manifest = Path(manifest)
    if output.exists():
        raise ValueError("Fresh compatibility output path required")
    ensure_validator()
    case = PREFIX + kind
    entries = json.loads(manifest.read_text())["cases"]
    if sum(entry["case_id"] == case for entry in entries) != 1:
        raise ValueError("Unknown exact comparison/audit case")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c158208-audit-fixtures"))
    command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"), "compatibility",
               "--manifest", str(manifest), "--case", case, "--output", str(output),
               "--library", str(ROOT / "runtime/library"), "--validator", str(VALIDATOR)]
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError("Fresh compatibility fixture failed: " + kind + "\n" + result.stdout[-2000:])
    receipt = json.loads((output / "compatibility.json").read_text())
    if receipt.get("case_id") != case or receipt.get("passed") is not True:
        raise ValueError("Fresh compatibility fixture receipt differs: " + kind)
    return output
