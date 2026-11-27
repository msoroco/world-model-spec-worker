"""Run exact current-runtime offline and source-bound compatibility proofs."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c412982-lvmc180-owner"
MANIFEST = HERE / "execution-manifest.draft.json"
PYTHON = ROOT / ".venv-cpu/bin/python"
VALIDATOR = ROOT / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def log(path, value):
    content = "\n".join(line.rstrip() for line in value.rstrip().splitlines())
    path.write_text(content + "\n" if content else "", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("proof log too large: " + str(path))


def run(command, saved_log, env):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    log(saved_log, result.stdout)
    if result.returncode:
        raise ValueError("proof failed: " + str(saved_log) + "\n" +
                         result.stdout[-2000:])
    return result


def prove(tag):
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "output")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMPDIR"] = str(SCRATCH / "tmp")
    for name in ("output", "tmp", tag):
        (SCRATCH / name).mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        slug = case_id.removeprefix(HERE.name + "__")
        offline = SCRATCH / tag / "offline" / slug
        offline.parent.mkdir(parents=True, exist_ok=True)
        command = [PYTHON, ROOT / "runtime.py", "offline", "--manifest", MANIFEST,
                   "--case", case_id, "--output", offline, "--python", PYTHON]
        run(command, HERE / ("proof-offline-" + slug + "-command.log"), env)
        offline_log = HERE / ("proof-offline-" + slug + ".log")
        log(offline_log, (offline / "offline.log").read_text())
        entry["offline"] = {"command": " ".join(str(x) for x in command),
                            "exit_code": 0, "construction_sha256":
                                entry["construction_sha256"],
                            "log": offline_log.name, "log_sha256": sha(offline_log)}
        compat = SCRATCH / tag / "compat" / slug
        compat.parent.mkdir(parents=True, exist_ok=True)
        command = [PYTHON, ROOT / "runtime.py", "compatibility", "--manifest",
                   MANIFEST, "--case", case_id, "--output", compat,
                   "--library", ROOT / "runtime/library", "--validator", VALIDATOR]
        run(command, HERE / ("proof-compat-" + slug + "-command.log"), env)
        analysis_log = HERE / ("proof-compat-" + slug + "-analysis.log")
        negative_log = HERE / ("proof-compat-" + slug + "-negative.log")
        receipt = HERE / ("proof-compat-" + slug + ".json")
        log(analysis_log, (compat / "compatibility-analysis.log").read_text())
        log(negative_log, (compat / "negative-analysis.log").read_text())
        shutil.copyfile(compat / "compatibility.json", receipt)
        entry["compatibility"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                  "log": analysis_log.name,
                                  "negative_log": negative_log.name}
        entry["negative"] = {"log": negative_log.name}
        print("passed", slug, "offline, positive and negative compatibility", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("all exact Fremont runtime proofs passed", len(manifest["cases"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    prove(args.tag)
