"""Refresh source-bound primary proofs after the body-footprint adapter correction."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = ".runtime-work/c229439-validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(parts, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work/hose-913-refresh"),
               HOSE_SCRATCH_ROOT=str(REPO / ".runtime-work/hose-913-scratch"))
    done = subprocess.run(parts, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout)
    if done.returncode:
        raise ValueError("proof command failed: " + " ".join(parts) + "\n" + done.stdout[-1500:])
    return " ".join(parts)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest["cases"]:
        cid = case["case_id"]
        short = cid.removeprefix(ROOT.name + "__")
        folder = ROOT / "cases" / short
        source = ROOT / case["construction"]
        digest = sha(source)
        case["construction_sha256"] = digest
        case["offline"]["construction_sha256"] = digest
        physical = folder / "physical-preparation.json"
        proof = json.loads(physical.read_text())
        proof["construction_sha256"] = digest
        physical.write_text(json.dumps(proof, indent=2) + "\n")
        case["physical_preparation"]["sha256"] = sha(physical)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        offline_out = ".runtime-work/hose-913-selected-" + short + "-v16"
        offline = [sys.executable, "runtime.py", "offline", "--manifest", str(MANIFEST.relative_to(REPO)),
                   "--case", cid, "--output", offline_out]
        offline_log = folder / "selected-offline.log"
        case["offline"].update(command=run(offline, offline_log), exit_code=0,
                               log_sha256=sha(offline_log))
        compat_out = ".runtime-work/hose-913-compat-" + short + "-v4"
        compatible = [sys.executable, "runtime.py", "compatibility", "--manifest", str(MANIFEST.relative_to(REPO)),
                      "--case", cid, "--output", compat_out, "--library", "runtime/library",
                      "--validator", VALIDATOR]
        run(compatible, folder / "compatibility-command.log")
        generated = REPO / compat_out
        receipt = json.loads((generated / "compatibility.json").read_text())
        if receipt["construction_sha256"] != digest or receipt["case_id"] != cid:
            raise ValueError("current compatibility construction differs")
        for old, new in (("compatibility.json", "compatibility.json"),
                         ("compatibility-analysis.log", "cpu-compatibility-analysis.log"),
                         ("negative-analysis.log", "negative-analysis.log")):
            shutil.copyfile(generated / old, folder / new)
        case["compatibility"] = {"receipt": "cases/" + short + "/compatibility.json",
                                 "sha256": sha(folder / "compatibility.json"),
                                 "log": "cases/" + short + "/cpu-compatibility-analysis.log"}
        case["negative"] = {"log": "cases/" + short + "/negative-analysis.log"}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(short, "current primary proofs refreshed", flush=True)


if __name__ == "__main__":
    main()
