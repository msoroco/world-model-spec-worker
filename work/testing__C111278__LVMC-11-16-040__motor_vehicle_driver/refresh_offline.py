"""Run and pin every exact primary and fallback offline construction."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    py = str(REPO / ".venv-cpu/bin/python")
    runtime = str(REPO / "runtime.py")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       TMPDIR=str(REPO / ".runtime-work/c111278-owner/tmp"),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/c111278-owner/pipeline"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate_id, item in (("primary", entry), ("fallback1", entry["candidates"][0])):
            base = REPO / ".runtime-work/c111278-owner"
            version = 0
            while True:
                output = base / f"offline-{suffix}-{candidate_id}-{version}"
                if not output.exists():
                    break
                version += 1
            command = [py, runtime, "offline", "--manifest", str(MANIFEST),
                       "--case", entry["case_id"], "--candidate", candidate_id,
                       "--output", str(output), "--python", py]
            run = subprocess.run(command, env=environment, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if run.returncode:
                raise RuntimeError(f"{suffix}/{candidate_id}: {run.stdout[-2000:]}")
            raw = (output / "offline.log").read_text()
            log = ROOT / f"proof-offline-{suffix}-{candidate_id}.log"
            log.write_text("\n".join(line.rstrip() for line in raw.splitlines()).rstrip() + "\n")
            item["offline"] = {"exit_code": 0,
                               "construction_sha256": item["construction_sha256"],
                               "command": " ".join(command), "log": log.name,
                               "log_sha256": sha(log)}
            print(suffix, candidate_id, "passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
