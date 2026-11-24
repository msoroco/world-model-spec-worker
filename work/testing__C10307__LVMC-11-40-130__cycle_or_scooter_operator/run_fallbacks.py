"""Prove each camera fallback with exact offline and source-shaped compatibility."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
MANIFEST = OWN / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"
VALIDATOR = REPO / ".runtime-work/c10307-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> int:
    with log.open("w") as stream:
        completed = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                   stdout=stream, stderr=subprocess.STDOUT, timeout=300)
    return completed.returncode


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        short = entry["case_id"].removeprefix(manifest["assignment_id"] + "__")
        candidate = entry["candidates"][0]
        prefix = f"cpu-fallback1-{short}"
        output = REPO / ".runtime-work" / f"c10307-fallback1-offline-v12-{short}"
        command = [str(PYTHON), str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--candidate", "fallback1", "--output", str(output),
                   "--python", str(PYTHON)]
        log = OWN / f"{prefix}-offline.log"
        exit_code = run(command, log)
        candidate["offline"] = {"command": " ".join(command), "exit_code": exit_code,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": log.name, "log_sha256": sha(log)}
        if exit_code:
            raise RuntimeError(f"offline fallback failed for {short}: {log}")
        output = REPO / ".runtime-work" / f"c10307-fallback1-compat-v12-{short}"
        command = [str(PYTHON), str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--candidate", "fallback1", "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        log = OWN / f"{prefix}-compat.log"
        exit_code = run(command, log)
        if exit_code:
            raise RuntimeError(f"compatibility fallback failed for {short}: {log}")
        copies = {"compatibility.json": f"{prefix}-compatibility.json",
                  "compatibility-analysis.log": f"{prefix}-compat-analysis.log",
                  "negative-analysis.log": f"{prefix}-negative-analysis.log"}
        for source, destination in copies.items():
            (OWN / destination).write_bytes((output / source).read_bytes())
        candidate["compatibility"] = {"receipt": copies["compatibility.json"],
                                      "sha256": sha(OWN / copies["compatibility.json"]),
                                      "log": copies["compatibility-analysis.log"],
                                      "negative_log": copies["negative-analysis.log"]}
        print(short, "offline and compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
