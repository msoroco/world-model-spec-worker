"""Reprove the four staged alternative bundles against the pinned runtime."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
MANIFEST = ROOT / "alternative-offline-manifest.json"


def main():
    manifest = json.loads(MANIFEST.read_text())
    for index, entry in enumerate(manifest["cases"]):
        output = REPO / ".runtime-work" / f"c215286-alt-{index}-physical-context-20261124"
        command = [sys.executable, str(REPO / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--output", str(output)]
        log = ROOT / f"alternative-{index}-offline.log"
        with log.open("w") as stream:
            process = subprocess.run(command, cwd=REPO, stdout=stream,
                                     stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                     check=False)
        if process.returncode:
            raise RuntimeError(f"Offline failed for {entry['case_id']}: {log}")
        entry["offline"].update({
            "command": " ".join(command), "exit_code": 0,
            "log": log.name,
            "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        })
        print(entry["case_id"], "offline passed")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
