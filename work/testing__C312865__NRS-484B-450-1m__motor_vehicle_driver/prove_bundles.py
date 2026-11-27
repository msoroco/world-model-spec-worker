"""Run current-runtime exact primary/fallback offline and compatibility proofs."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SCRATCH = ROOT / ".runtime-work/c312865-nov27/proofs-v5"
VALIDATOR = ROOT / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"
MANIFEST = HERE / "execution-manifest.json"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(args, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout.rstrip() + "\n")
    if done.returncode:
        raise ValueError("exact CPU proof failed: " + log.name + "; " + done.stdout[-1200:])
    return done


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError("current Lean validator missing")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        for variant in ("primary", "fallback1"):
            selected = entry if variant == "primary" else entry["candidates"][0]
            tag = suffix + "-" + variant
            offline = SCRATCH / ("offline-" + tag)
            compatible = SCRATCH / ("compatible-" + tag)
            if offline.exists() or compatible.exists():
                raise ValueError("retain prior proof output; choose fresh version: " + tag)
            base = [sys.executable, str(ROOT / "runtime.py")]
            option = [] if variant == "primary" else ["--candidate", variant]
            offline_command = base + ["offline", "--manifest", str(MANIFEST),
                                      "--case", entry["case_id"], "--output", str(offline),
                                      "--python", sys.executable] + option
            offline_log = HERE / ("proof-offline-" + tag + ".log")
            command(offline_command, offline_log)
            selected["offline"] = {"command": " ".join(offline_command), "exit_code": 0,
                                   "log": offline_log.name, "log_sha256": digest(offline_log),
                                   "construction_sha256": selected["construction_sha256"]}
            compat_command = base + ["compatibility", "--manifest", str(MANIFEST),
                                     "--case", entry["case_id"], "--output", str(compatible),
                                     "--library", str(ROOT / "runtime/library"),
                                     "--validator", str(VALIDATOR)] + option
            compat_log = HERE / ("proof-compat-command-" + tag + ".log")
            command(compat_command, compat_log)
            receipt = HERE / ("proof-compat-receipt-" + tag + ".json")
            analysis = HERE / ("proof-compat-analysis-" + tag + ".log")
            negative = HERE / ("proof-compat-negative-" + tag + ".log")
            shutil.copyfile(compatible / "compatibility.json", receipt)
            shutil.copyfile(compatible / "compatibility-analysis.log", analysis)
            shutil.copyfile(compatible / "negative-analysis.log", negative)
            proof = json.loads(receipt.read_text())
            if proof.get("passed") is not True or proof.get("construction_sha256") != selected["construction_sha256"]:
                raise ValueError("compatibility source binding differs: " + tag)
            selected["compatibility"] = {"receipt": receipt.name, "sha256": digest(receipt),
                                         "log": analysis.name, "negative_log": negative.name}
            if variant == "primary":
                entry["negative"] = {"log": negative.name}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print("proved", entry["case_id"], flush=True)


if __name__ == "__main__":
    main()
