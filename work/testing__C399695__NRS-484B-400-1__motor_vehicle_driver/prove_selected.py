"""Run five current-hash offline, compatibility and saved-only CPU proofs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work/c399695-4001-owner/selected-v1"
VALIDATOR = ROOT / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(path, value):
    path.write_text(value.rstrip() + "\n")


def execute(command, destination):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log(destination, result.stdout)
    if result.returncode:
        raise ValueError("pinned selected proof failed: " + destination.name)
    return json.loads(result.stdout)


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError("pinned Lean validator executable missing")
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest["cases"]) != 5:
        raise ValueError("five exact right-turn-position cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        offline = SCRATCH / "offline" / suffix
        compatible = SCRATCH / "compatible" / suffix
        saved = SCRATCH / "saved" / suffix
        if offline.exists() or compatible.exists() or saved.exists():
            raise ValueError("retain prior proof generation; use fresh scratch version")
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(offline), "--python", sys.executable]
        receipt = execute(command, HERE / ("proof-selected-offline-" + suffix + ".log"))
        if receipt.get("offline_passed") is not True or receipt.get("simulation_started") is not False:
            raise ValueError("offline proof did not remain CPU only")
        offline_log = HERE / ("proof-selected-offline-" + suffix + ".log")
        entry["offline"] = {"command": " ".join(command), "exit_code": 0,
                            "log": offline_log.name, "log_sha256": sha(offline_log),
                            "construction_sha256": entry["construction_sha256"]}
        command = [sys.executable, str(ROOT / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(compatible), "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        execute(command, HERE / ("proof-compat-command-" + suffix + ".log"))
        for source, target in (("compatibility.json", "proof-compat-receipt-" + suffix + ".json"),
                               ("compatibility-analysis.log", "proof-compat-analysis-" + suffix + ".log"),
                               ("negative-analysis.log", "proof-compat-negative-" + suffix + ".log")):
            raw = (compatible / source).read_text()
            (HERE / target).write_text(raw.rstrip() + "\n" if raw.strip() else "")
        command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--attempt", str(compatible), "--output", str(saved),
                   "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        result = execute(command, HERE / ("proof-selected-saved-" + suffix + ".log"))
        if not (result.get("passed") is True and result.get("recorded_only") is True and
                result.get("originals_preserved") is True):
            raise ValueError("saved-only proof did not preserve originals")
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("selected right-turn-lane CPU proofs:", run())
