"""Run exact source-bound primary/fallback CPU compatibility proofs."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work"
VALIDATOR = SCRATCH / "c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_one(entry, candidate):
    suffix = entry["case_id"].split("__")[-1]
    directory = SCRATCH / ("c147339-compat-v2-" + suffix + "-" + candidate)
    if not (directory / "compatibility.json").is_file():
        if directory.exists():
            raise ValueError("Retain prior failed attempt: " + str(directory))
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--candidate", candidate, "--output", str(directory),
                   "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "c147339-runtime"),
                   PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "c147339-tmp"))
        cli_log = SCRATCH / ("c147339-cli-v2-" + suffix + "-" + candidate + ".log")
        with cli_log.open("w") as log:
            completed = subprocess.run(command, cwd=REPO, env=env, stdout=log,
                                       stderr=subprocess.STDOUT)
        if completed.returncode:
            raise RuntimeError("Compatibility failure: " + suffix + " " + candidate +
                               " see " + str(cli_log))
    return suffix, candidate, directory


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jobs = [(entry, candidate) for entry in manifest["cases"]
            for candidate in ("primary", "fallback1")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_one, entry, candidate) for entry, candidate in jobs]
        completed = []
        for future in concurrent.futures.as_completed(futures):
            completed.append(future.result())
            print(completed[-1][0], completed[-1][1], "passed", flush=True)
    for suffix, candidate, directory in completed:
        entry = next(item for item in manifest["cases"] if item["case_id"].endswith("__" + suffix))
        names = {"receipt": "cpu-compatibility-receipt-" + suffix + "-" + candidate + ".json",
                 "log": "cpu-compatibility-" + suffix + "-" + candidate + ".log",
                 "negative_log": "cpu-compatibility-negative-" + suffix + "-" + candidate + ".log"}
        for key, source in (("receipt", "compatibility.json"),
                            ("log", "compatibility-analysis.log"),
                            ("negative_log", "negative-analysis.log")):
            (ROOT / names[key]).write_bytes((directory / source).read_bytes())
        spec = {**names, "sha256": sha(ROOT / names["receipt"])}
        if candidate == "primary":
            entry["compatibility"] = spec
            entry["negative"] = {"log": names["negative_log"]}
        else:
            entry["candidates"][0]["compatibility"] = spec
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
