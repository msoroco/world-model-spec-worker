"""Run every exact offline and positive/negative compatibility proof."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c412262-490-case-proofs-v1"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, env):
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(shlex.join(command) + "\n" + (result.stdout + result.stderr)[-3000:])
    return result


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    temp = ROOT / "tmp"
    temp.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(temp),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[1]
        offline = ROOT / "offline" / tag
        compat = ROOT / "compat" / tag
        for path in (offline, compat):
            if path.exists():
                shutil.rmtree(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "runtime.py", "offline", "--manifest", str(MANIFEST),
                   "--case", case_id, "--output", str(offline), "--python", sys.executable]
        run(command, env)
        log = HERE / ("cpu-offline-" + tag + ".log")
        log.write_text((offline / "offline.log").read_text().rstrip() + "\n")
        entry["offline"] = {"command": shlex.join(command), "construction_sha256": entry["construction_sha256"],
                            "exit_code": 0, "log": log.name, "log_sha256": sha(log)}
        command = [sys.executable, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
                   "--case", case_id, "--output", str(compat), "--library", "runtime/library",
                   "--validator", str(VALIDATOR)]
        run(command, env)
        receipt = HERE / ("cpu-compat-" + tag + "-receipt.json")
        analysis = HERE / ("cpu-compat-" + tag + "-analysis.log")
        negative = HERE / ("cpu-compat-" + tag + "-negative.log")
        shutil.copyfile(compat / "compatibility.json", receipt)
        shutil.copyfile(compat / "compatibility-analysis.log", analysis)
        shutil.copyfile(compat / "negative-analysis.log", negative)
        if analysis.read_bytes().endswith(b"\n\n") or negative.read_bytes().endswith(b"\n\n"):
            raise RuntimeError("generated compatibility log has blank EOF")
        entry["compatibility"] = {"command": shlex.join(command), "receipt": receipt.name,
                                   "sha256": sha(receipt), "log": analysis.name,
                                   "negative_log": negative.name,
                                   "negative_log_sha256": sha(negative)}
        entry["negative"] = {"log": negative.name, "log_sha256": sha(negative)}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(tag, "offline and compatibility passed", flush=True)


if __name__ == "__main__":
    main()
