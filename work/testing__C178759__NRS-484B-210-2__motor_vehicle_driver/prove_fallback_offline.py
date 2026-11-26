"""Run pinned offline checks for each source-hashed physical fallback."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work" / "c178759-owner-nov26" / "right-pass-fallback-offline-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1" or sha(HERE / candidate["construction"]) != candidate["construction_sha256"]:
            raise ValueError("fallback construction changed")
        destination = SCRATCH / suffix
        if destination.exists():
            raise ValueError("retain previous fallback proof; select fresh scratch")
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--candidate", "fallback1", "--output", str(destination),
                   "--python", sys.executable]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / ("proof-fallback-offline-" + suffix + ".log")
        detail = (destination / "offline.log").read_text() if (destination / "offline.log").is_file() else ""
        log.write_text((result.stdout.rstrip() + "\n" + detail.rstrip()).strip() + "\n")
        if result.returncode:
            raise ValueError("fallback offline failed: " + entry["case_id"])
        receipt = json.loads(result.stdout)
        if receipt.get("offline_passed") is not True or receipt.get("simulation_started") is not False:
            raise ValueError("fallback offline receipt incomplete")
        candidate["offline"] = {"command": " ".join(command), "exit_code": 0,
                                "log": log.name, "log_sha256": sha(log),
                                "construction_sha256": candidate["construction_sha256"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("fallback exact offline proofs:", run())
