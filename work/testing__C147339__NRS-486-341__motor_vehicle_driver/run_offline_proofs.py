"""Run all exact primary and fallback bundles without CARLA."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work" / "c147339-offline-proofs-v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate in ("primary", "fallback1"):
            destination = SCRATCH / (suffix + "-" + candidate)
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--candidate", candidate, "--output", str(destination)]
            if destination.exists():
                raise ValueError("Retain prior offline attempt: " + str(destination))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       TMPDIR=str(REPO / ".runtime-work" / "c147339-tmp"))
            result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            if result.returncode:
                print(result.stdout, result.stderr)
                raise RuntimeError("Offline failure: " + suffix + " " + candidate)
            log = ROOT / ("cpu-offline-" + suffix + "-" + candidate + ".log")
            log.write_text((destination / "offline.log").read_text(encoding="utf-8").rstrip() + "\n",
                           encoding="utf-8")
            proof = {"command": " ".join(command), "exit_code": 0,
                     "construction_sha256": entry["construction_sha256"] if candidate == "primary"
                     else entry["candidates"][0]["construction_sha256"],
                     "log": log.name, "log_sha256": sha(log)}
            if candidate == "primary":
                entry["offline"] = proof
            else:
                entry["candidates"][0]["offline"] = proof
            print(suffix, candidate, "passed")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
