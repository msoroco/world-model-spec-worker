"""Bind successful exact CPU offline receipts to the draft manifest."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c378707-root"
VERSION = os.environ.get("C378707_OFFLINE_VERSION", "v5")
MANIFEST = ROOT / "execution-manifest.json"


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for row in manifest["cases"]:
        variant = row["case_id"].removeprefix(manifest["assignment_id"] + "__")
        for candidate, target in ((None, row), ("fallback1", row["candidates"][0])):
            label = variant + ("-fallback1" if candidate else "")
            destination = SCRATCH / ("offline-" + label + "-" + VERSION)
            raw_log = (destination / "offline.log").read_text()
            if (f'"case_id": "{row["case_id"]}"' not in raw_log or
                    '"offline_check": "passed"' not in raw_log or
                    not raw_log.rstrip().endswith("OK")):
                raise ValueError("offline receipt did not pass: " + label)
            content = "\n".join(line.rstrip() for line in raw_log.splitlines()).rstrip() + "\n"
            log = ROOT / ("cpu-offline-" + label + ".log")
            log.write_text(content)
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", row["case_id"],
                       "--output", str(destination), "--python", str(REPO / ".venv-cpu/bin/python")]
            if candidate:
                command += ["--candidate", candidate]
            target["offline"] = {"command": " ".join(command), "construction_sha256": target["construction_sha256"],
                                 "exit_code": 0, "log": log.name,
                                 "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    bind()
