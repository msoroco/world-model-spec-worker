"""Run exact runtime offline materialization for every planned primary bundle."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "execution-manifest.draft.json"
OUTPUT = ROOT / ".runtime-work" / "c229813-owner" / "offline-nine-v1"


def main():
    entries = json.loads(MANIFEST.read_text())["cases"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    receipts = []
    for entry in entries:
        case_id = entry["case_id"]
        suffix = case_id.split("__")[-1]
        destination = OUTPUT / suffix
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--output", str(destination)]
        run = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                             capture_output=True, text=True)
        log = PACKAGE / ("proof-offline-" + suffix + ".log")
        log.write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise SystemExit("exact offline failed: " + case_id + " (" + str(log) + ")")
        receipts.append({"case_id": case_id, "candidate_id": "primary",
                         "exit_code": 0, "command": " ".join(command),
                         "construction_sha256": entry["construction_sha256"],
                         "log": log.name,
                         "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
    (PACKAGE / "cpu-offline-proofs.json").write_text(
        json.dumps(receipts, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"passed": len(receipts)}))


if __name__ == "__main__":
    main()
