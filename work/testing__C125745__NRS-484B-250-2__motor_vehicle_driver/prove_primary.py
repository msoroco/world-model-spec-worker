"""Pin exact offline and positive/missing-source compatibility for three probes."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c125745-250-2"
PYTHON = str(REPO / ".venv-cpu/bin/python")
VALIDATOR = str(REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log, env):
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip() + "\n")
    if result.returncode:
        raise ValueError("proof failed: " + " ".join(args) + "\n" + result.stdout[-1400:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        offline_dir = SCRATCH / ("offline-" + suffix + "-v6")
        offline_log = ROOT / ("cpu-offline-" + suffix + "-v6.log")
        args = [PYTHON, "runtime.py", "offline", "--manifest", str(MANIFEST),
                "--case", case, "--output", str(offline_dir)]
        run(args, offline_log, env)
        entry["offline"] = {"command": " ".join(args), "exit_code": 0,
                            "construction_sha256": entry["construction_sha256"],
                            "log": offline_log.name, "log_sha256": sha(offline_log)}
        compat_dir = SCRATCH / ("compat-" + suffix + "-v6")
        compat_log = ROOT / ("cpu-compat-analysis-" + suffix + "-v6.log")
        args = [PYTHON, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
                "--case", case, "--output", str(compat_dir),
                "--library", str(REPO / "runtime/library"), "--validator", VALIDATOR]
        run(args, compat_log, env)
        shutil.copy2(compat_dir / "compatibility-analysis.log", compat_log)
        negative = ROOT / ("cpu-compat-negative-" + suffix + "-v6.log")
        shutil.copy2(compat_dir / "negative-analysis.log", negative)
        receipt = ROOT / ("cpu-compat-" + suffix + "-v6.json")
        shutil.copy2(compat_dir / "compatibility.json", receipt)
        entry["compatibility"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                  "log": compat_log.name, "negative_log": negative.name}
        entry["negative"] = {"log": negative.name}
        print(suffix + " exact offline and compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
