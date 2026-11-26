"""Run pinned offline construction checks for all fourteen selected cases."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work" / "c228989-owner-nov26" / "selected-offline-v7"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(manifest["cases"]) != 14:
        raise ValueError("all fourteen selected cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        destination = SCRATCH / suffix
        if destination.exists():
            raise ValueError("retain prior offline proof; choose a fresh proof generation")
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(destination), "--python", sys.executable]
        env = dict(os.environ)
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
        env["TMPDIR"] = str(SCRATCH)
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / ("proof-selected-offline-" + suffix + ".log")
        detail = (destination / "offline.log").read_text(encoding="utf-8") if (destination / "offline.log").is_file() else ""
        log.write_text((result.stdout.rstrip() + "\n" + detail.rstrip()).strip() + "\n",
                       encoding="utf-8")
        if result.returncode != 0:
            raise ValueError("selected offline proof failed: " + entry["case_id"])
        receipt = json.loads(result.stdout)
        if receipt.get("offline_passed") is not True or receipt.get("simulation_started") is not False:
            raise ValueError("offline runner did not certify CPU-only check")
        entry["offline"] = {"command": " ".join(command), "exit_code": 0,
                            "log": log.name, "log_sha256": sha(log),
                            "construction_sha256": entry["construction_sha256"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("selected offline proofs:", run())
