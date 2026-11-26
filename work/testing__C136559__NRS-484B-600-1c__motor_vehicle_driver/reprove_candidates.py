"""Run exact offline and pinned compatibility for both engineering candidates."""
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
SCRATCH = REPO / ".runtime-work/c136559-600-1c"
VALIDATOR = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log, env):
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip() + "\n")
    if result.returncode:
        raise ValueError("proof failed: " + " ".join(args) + "\n" + result.stdout[-1600:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    (SCRATCH / "tmp").mkdir(parents=True, exist_ok=True)
    (SCRATCH / "output").mkdir(parents=True, exist_ok=True)
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        for candidate_id, holder in [("primary", entry),
                                     ("fallback1", entry["candidates"][0])]:
            label = suffix + "-" + candidate_id
            offline_dir = SCRATCH / ("offline-" + label + "-v5")
            offline_log = ROOT / ("cpu-offline-" + label + "-v5.log")
            args = [str(REPO / ".venv-cpu/bin/python"), "runtime.py", "offline",
                    "--manifest", str(MANIFEST), "--case", entry["case_id"],
                    "--candidate", candidate_id, "--output", str(offline_dir)]
            run(args, offline_log, env)
            holder["offline"] = {"command": " ".join(args), "exit_code": 0,
                                 "construction_sha256": holder["construction_sha256"],
                                 "log": offline_log.name, "log_sha256": sha(offline_log)}
            compat_dir = SCRATCH / ("compat-" + label + "-v4")
            compat_log = ROOT / ("cpu-compat-analysis-" + label + "-v4.log")
            args = [str(REPO / ".venv-cpu/bin/python"), "runtime.py", "compatibility",
                    "--manifest", str(MANIFEST), "--case", entry["case_id"],
                    "--candidate", candidate_id, "--output", str(compat_dir),
                    "--library", str(REPO / "runtime/library"),
                    "--validator", str(VALIDATOR)]
            run(args, compat_log, env)
            receipt = json.loads((compat_dir / "compatibility.json").read_text())
            receipt_path = ROOT / ("cpu-compat-" + label + "-v4.json")
            # The runtime receipt references its own positive and negative log hashes.
            shutil.copy2(compat_dir / "compatibility-analysis.log", compat_log)
            negative_log = ROOT / ("cpu-compat-negative-" + label + "-v4.log")
            shutil.copy2(compat_dir / "negative-analysis.log", negative_log)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            holder["compatibility"] = {"receipt": receipt_path.name,
                                        "sha256": sha(receipt_path),
                                        "log": compat_log.name,
                                        "negative_log": negative_log.name}
            if candidate_id == "primary":
                entry["negative"] = {"log": negative_log.name}
            print(label + " offline/compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
