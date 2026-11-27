"""Bind exact primary/fallback offline and compatibility receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work" / "c177249-compat-all-v2"
OFFLINE = REPO / ".runtime-work" / "c177249-offline-v3"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, source):
    target = HERE / name
    temporary = SCRATCH / (name + ".tmp")
    temporary.write_text(Path(source).read_text().rstrip() + "\n")
    os.replace(temporary, target)
    return target


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id.removeprefix(HERE.name + "__")
        for candidate in ("primary", "fallback1"):
            tag = name + "-" + candidate
            output = SCRATCH / tag
            if output.exists():
                raise ValueError("compatibility scratch already exists: " + tag)
            command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", case_id,
                       "--output", str(output), "--library", str(REPO / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            if candidate != "primary":
                command.extend(("--candidate", candidate))
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                     env={**os.environ, "TMPDIR": str(REPO / ".runtime-work"),
                                          "MPLCONFIGDIR": str(REPO / ".runtime-work/mpl")})
            (SCRATCH / (tag + ".command.log")).write_text(process.stdout + process.stderr)
            if process.returncode:
                raise ValueError("compatibility failed: " + tag + "; inspect scratch command log")
            analysis = save("cpu-compat-" + tag + "-analysis.log", output / "compatibility-analysis.log")
            negative = save("cpu-compat-" + tag + "-negative.log", output / "negative-analysis.log")
            receipt = save("cpu-compat-" + tag + "-receipt.json", output / "compatibility.json")
            compat = {"command": " ".join(command), "log": analysis.name,
                      "negative_log": negative.name, "receipt": receipt.name,
                      "sha256": sha(receipt), "negative_log_sha256": sha(negative)}
            offline_log = HERE / ("cpu-offline-" + tag + ".log")
            if not offline_log.is_file():
                raise ValueError("exact offline proof missing: " + tag)
            offline_command = [sys.executable, str(REPO / "runtime.py"), "offline",
                               "--manifest", str(MANIFEST), "--case", case_id,
                               "--candidate", candidate,
                               "--output", str(OFFLINE / tag)]
            target = entry if candidate == "primary" else entry["candidates"][0]
            target["offline"] = {"command": " ".join(offline_command),
                                 "construction_sha256": target["construction_sha256"],
                                 "log": offline_log.name, "log_sha256": sha(offline_log),
                                 "exit_code": 0}
            target["compatibility"] = compat
            if candidate == "primary":
                entry["negative"] = {"log": negative.name, "log_sha256": sha(negative)}
            print(tag, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    run()
