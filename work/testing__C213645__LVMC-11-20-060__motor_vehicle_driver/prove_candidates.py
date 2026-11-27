"""Build one physical fallback and bind exact offline/compatibility CPU receipts."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c213645-owner"
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c229405-decoder2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def clean_copy(source, target):
    data = Path(source).read_text().rstrip()
    target.write_text(data + "\n" if data else "")


def execute(command, output):
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH / "tmp"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / "pipeline"))
    with output.open("w") as log:
        result = subprocess.run(command, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError("CPU proof failed: " + " ".join(command) + " (see " + str(output) + ")")


manifest = json.loads(MANIFEST.read_text())
for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    primary = json.loads((HERE / entry["construction"]).read_text())
    fallback = copy.deepcopy(primary)
    config_entry = next(row for row in fallback["files"] if row["path"] == "config.json")
    config = json.loads(config_entry["content"])
    config["fallback_spawn_offset_m"] = .5
    config_entry["content"] = json.dumps(config, indent=2) + "\n"
    fallback_path = HERE / "cases" / name / "fallback1-construction.json"
    write(fallback_path, fallback)
    entry["candidates"] = [{
        "id": "fallback1", "construction": str(fallback_path.relative_to(HERE)),
        "construction_sha256": sha(fallback_path),
        "trigger": {"source": "reviewed original spawn probe and CARLA spawn result",
                    "metric": "ego spawn collision clearance in meters",
                    "failure_condition": "primary spawn rejected or measured clearance below 0.5 m"},
        "changed_knobs": ["ego spawn height offset raised from 0 to 0.5 m within reviewed driveway envelope"],
    }]
write(MANIFEST, manifest)

for entry in manifest["cases"]:
    name = entry["case_id"].split("__")[-1]
    primary = json.loads((HERE / entry["construction"]).read_text())
    acquisition = {}
    for channel in primary["recording_description"]["channels"]:
        key = channel["name"]
        method = ("Session.geometry_packet" if "geometry" in key or "district" in key else
                  "Session.activity" if "motion" in key or "vehicle" in key else "capture")
        acquisition[key] = {"entrypoint": "carla_driveway_adapter.py" if method != "capture" else "native_acquisition.py",
                            "method": method, "evidence": "original Native frame-joined source packet and camera image readback"}
    entry["acquisition"] = acquisition
    for candidate in ("primary", "fallback1"):
        selected = entry if candidate == "primary" else entry["candidates"][0]
        output = SCRATCH / ("offline-" + name + "-" + candidate + "-final")
        command = [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--output", str(output), "--python", sys.executable,
                   "--candidate", candidate]
        execute(command, SCRATCH / ("offline-" + name + "-" + candidate + "-final.stdout"))
        log = HERE / ("cpu-offline-" + name + "-" + candidate + ".log")
        clean_copy(output / "offline.log", log)
        selected["offline"] = {"command": " ".join(command), "exit_code": 0, "log": log.name,
                               "log_sha256": sha(log), "construction_sha256": selected["construction_sha256"]}
        write(MANIFEST, manifest)
        output = SCRATCH / ("compat-" + name + "-" + candidate + "-final")
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                   "--case", entry["case_id"], "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR), "--candidate", candidate]
        execute(command, SCRATCH / ("compat-" + name + "-" + candidate + "-final.stdout"))
        receipt = json.loads((output / "compatibility.json").read_text())
        log = HERE / ("cpu-compat-" + name + "-" + candidate + ".log")
        negative = HERE / ("cpu-compat-" + name + "-" + candidate + "-negative.log")
        clean_copy(output / "compatibility-analysis.log", log)
        clean_copy(output / "negative-analysis.log", negative)
        receipt["log_sha256"] = sha(log)
        receipt["negative_log_sha256"] = sha(negative)
        receipt_path = HERE / ("cpu-compat-" + name + "-" + candidate + ".json")
        write(receipt_path, receipt)
        selected["compatibility"] = {"receipt": receipt_path.name, "sha256": sha(receipt_path),
                                     "log": log.name, "negative_log": negative.name}
        if candidate == "primary":
            entry["negative"] = {"log": negative.name}
        write(MANIFEST, manifest)
        print(name, candidate, "offline+compatibility passed", flush=True)
