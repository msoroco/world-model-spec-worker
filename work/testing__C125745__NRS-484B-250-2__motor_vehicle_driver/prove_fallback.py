"""Build and pin one timing-control alternative for each exact probe."""
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


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log, env):
    done = subprocess.run(args, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(done.stdout.rstrip() + "\n")
    if done.returncode:
        raise ValueError("proof failed: " + done.stdout[-1500:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "output"))
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        original = json.loads((ROOT / entry["construction"]).read_text())
        alternate = json.loads(json.dumps(original))
        alternate["candidate_id"] = "fallback1"
        config_file = next(item for item in alternate["files"] if item["path"] == "config.json")
        config = json.loads(config_file["content"])
        shift = -.5 if suffix == "entry_below" else .5
        config["control"] = {"ego_release_offset_s": shift,
                             "purpose": "engineering timing adjustment; requires original measurement"}
        config_file["content"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
        fallback_path = ROOT / "cases" / suffix / "fallback1" / "construction.json"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        dump(fallback_path, alternate)
        candidate = {"id": "fallback1", "construction": str(fallback_path.relative_to(ROOT)),
                     "construction_sha256": sha(fallback_path),
                     "trigger": {"source": "original-attempt/entry-timing-source.json",
                                 "metric": "abs(measured_ego_minus_other_entry_s - target_s)",
                                 "failure_condition": "greater than 0.25 s engineering capture tolerance; no legal inference"},
                     "changed_knobs": ["ego_release_offset_s"]}
        entry["candidates"] = [candidate]
    dump(MANIFEST, manifest)
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        candidate = entry["candidates"][0]
        offline_dir = SCRATCH / ("offline-" + suffix + "-fallback1-v2")
        offline_log = ROOT / ("cpu-offline-" + suffix + "-fallback1-v2.log")
        args = [PYTHON, "runtime.py", "offline", "--manifest", str(MANIFEST),
                "--case", case, "--candidate", "fallback1", "--output", str(offline_dir)]
        run(args, offline_log, env)
        candidate["offline"] = {"command": " ".join(args), "exit_code": 0,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": offline_log.name, "log_sha256": sha(offline_log)}
        compat_dir = SCRATCH / ("compat-" + suffix + "-fallback1-v2")
        capture_log = ROOT / ("cpu-compat-capture-" + suffix + "-fallback1-v2.log")
        args = [PYTHON, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
                "--case", case, "--candidate", "fallback1", "--output", str(compat_dir),
                "--library", str(REPO / "runtime/library"), "--validator", VALIDATOR]
        run(args, capture_log, env)
        compat_log = ROOT / ("cpu-compat-analysis-" + suffix + "-fallback1-v2.log")
        negative_log = ROOT / ("cpu-compat-negative-" + suffix + "-fallback1-v2.log")
        receipt = ROOT / ("cpu-compat-" + suffix + "-fallback1-v2.json")
        shutil.copy2(compat_dir / "compatibility-analysis.log", compat_log)
        shutil.copy2(compat_dir / "negative-analysis.log", negative_log)
        shutil.copy2(compat_dir / "compatibility.json", receipt)
        candidate["compatibility"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                      "log": compat_log.name, "negative_log": negative_log.name}
        print(suffix + " fallback offline/compatibility passed", flush=True)
    dump(MANIFEST, manifest)


if __name__ == "__main__":
    main()
