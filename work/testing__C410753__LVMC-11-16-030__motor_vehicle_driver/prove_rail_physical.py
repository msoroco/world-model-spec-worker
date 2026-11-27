"""Run all three source-backed CPU outcome fixtures for each exact rail case."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
MANIFEST = HERE / "execution-manifest.json"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def one(entry):
    key = entry["case_id"].removeprefix(HERE.name + "__")
    fixtures = []
    complete = None
    for kind in KINDS:
        output = HERE / f"physical-{key}-{kind}.json"
        command = [str(PYTHON), str(HERE / "rail_physical_probe.py"),
                   "--case", entry["case_id"], "--kind", kind,
                   "--output", str(output)]
        done = subprocess.run(command, cwd=REPO, env=os.environ,
                              capture_output=True, text=True)
        log = HERE / f"physical-{key}-{kind}.log"
        log.write_text((done.stdout + done.stderr).rstrip() + "\n")
        if done.returncode:
            raise RuntimeError(f"rail physical {key} {kind}: " + log.read_text()[-1800:])
        fixture = {"command": " ".join(command), "exit_code": 0,
                   "kind": kind, "log": log.name, "log_sha256": sha(log),
                   "result": output.name, "result_sha256": sha(output)}
        fixtures.append(fixture)
        if kind == "complete_motion":
            complete = fixture
    receipt = {"format": "worker-physical-preparation",
               "case_id": entry["case_id"],
               "construction_sha256": entry["construction_sha256"],
               "fixtures": fixtures,
               "scope": "synthetic CPU protocol only; no physical acceptance",
               "lifecycle": {"command": complete["command"],
                             "events": ["capture_finished", "encoders_closed",
                                        "restoration_verified", "native_exit",
                                        "owner_released", "saved_processing_started"],
                             "exit_code": 0, "log": complete["log"],
                             "log_sha256": complete["log_sha256"]}}
    path = HERE / f"physical-{key}-receipt.json"
    write(path, receipt)
    return entry["case_id"], {"receipt": path.name, "sha256": sha(path)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, entry) for entry in manifest["cases"]]
        bindings = {}
        for future in as_completed(futures):
            case_id, binding = future.result()
            bindings[case_id] = binding
            print("physical+lifecycle", case_id, "passed", flush=True)
    for entry in manifest["cases"]:
        entry["physical_preparation"] = bindings[entry["case_id"]]
    write(MANIFEST, manifest)


if __name__ == "__main__":
    main()
