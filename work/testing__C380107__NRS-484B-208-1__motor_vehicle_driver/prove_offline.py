"""Reprove all exact source-gated constructions through pinned runtime offline."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c380107-owner"
MANIFEST = HERE / "diagnostic-execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(entry):
    case = entry["case_id"]
    suffix = case.rsplit("__", 1)[-1]
    output = SCRATCH / ("offline-" + uuid.uuid4().hex)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH),
               MPLCONFIGDIR=str(SCRATCH / "mpl"), PYTHONDONTWRITEBYTECODE="1")
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "offline",
               "--manifest", str(MANIFEST), "--case", case, "--output", str(output)]
    process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    log = HERE / "cases" / suffix / "offline.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text((process.stdout + process.stderr).rstrip() + "\n", encoding="utf-8")
    return {"case_id": case, "exit_code": process.returncode,
            "log": str(log.relative_to(HERE)), "sha256": sha(log)}


def main():
    entries = json.loads(MANIFEST.read_text())["cases"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, entries))
    (HERE / "cpu-offline-summary.json").write_text(
        json.dumps({"cases": results, "format": "worker-exact-offline-proof-summary"},
                   indent=2, sort_keys=True) + "\n")
    for item in results:
        print(item["case_id"].rsplit("__", 1)[-1], item["exit_code"])
    if any(item["exit_code"] for item in results):
        raise ValueError("exact offline proof failed")


if __name__ == "__main__":
    main()
