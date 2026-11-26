"""Materialize and prove a reviewed alternate unit route for each exact case."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from emergency_construction import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c405341-2b/fallback-offline"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry, case in zip(manifest["cases"], CASES):
        if entry["case_id"] != AID + "__" + case.suffix:
            raise ValueError("fallback case order differs")
        primary = json.loads((HERE / entry["construction"]).read_text())
        candidate = json.loads(json.dumps(primary))
        config_row = next(row for row in candidate["files"] if row["path"] == "config.json")
        config = json.loads(config_row["content"])
        config["engineering"]["alternate_unit_route"] = True
        config["engineering"]["movement_start_s"] = 0.0 if case.cue == "already_moving" else 16.5
        config_row["content"] = json.dumps(config, indent=2) + "\n"
        path = HERE / ("construction-" + case.suffix + "-fallback1.json")
        write(path, candidate)
        entry["candidates"] = [{"id": "fallback1", "construction": path.name,
            "construction_sha256": sha(path),
            "trigger": {"source": "original unit route and driver-view pixels",
                        "metric": "route connectedness and cue visibility on original frames",
                        "failure_condition": "primary route or view does not realize the requested cue"},
            "changed_knobs": ["require a separately reviewed connected alternate unit route",
                              "start movement 0.5 s earlier for additional view opportunity"]}]
    write(manifest_path, manifest)
    environment = dict(os.environ,
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c405341-2b/output-root"),
        TMPDIR=str(ROOT / ".runtime-work/c405341-2b/tmp"), PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        name = entry["case_id"].removeprefix(AID + "__")
        destination = SCRATCH / name
        if destination.exists():
            shutil.rmtree(destination)
        command = [sys.executable, str(ROOT / "runtime.py"), "offline",
                   "--manifest", str(manifest_path), "--case", entry["case_id"],
                   "--candidate", "fallback1", "--output", str(destination),
                   "--python", sys.executable]
        done = subprocess.run(command, cwd=ROOT, env=environment,
                              capture_output=True, text=True, timeout=300)
        log = HERE / ("cpu-offline-" + name + "-fallback1.log")
        details = (destination / "offline.log").read_text() if (destination / "offline.log").is_file() else ""
        log.write_text((details + done.stdout + done.stderr).rstrip() + "\n", encoding="utf-8")
        if done.returncode:
            raise RuntimeError("fallback offline failed: " + name + ": " + log.read_text()[-700:])
        item = entry["candidates"][0]
        item["offline"] = {"command": " ".join(command), "exit_code": 0,
                           "construction_sha256": item["construction_sha256"],
                           "log": log.name, "log_sha256": sha(log)}
        print(name, "fallback offline passed", flush=True)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
