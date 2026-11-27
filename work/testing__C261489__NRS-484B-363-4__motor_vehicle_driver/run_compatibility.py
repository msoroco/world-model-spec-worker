"""Exercise every exact selected saved finalizer and missing-source rejection."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
MANIFEST = HERE / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work" / "c261489-owner-nov27b"
VALIDATOR = REPO / ".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_copy(source: Path, destination: Path) -> None:
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id[len(ASSIGNMENT) + 2:]
        output = SCRATCH / ("compat-" + name + "-v3")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "compatibility", "--manifest", str(MANIFEST), "--case", case_id,
                   "--output", str(output), "--library", str(REPO / "runtime/library"),
                   "--validator", str(VALIDATOR)]
        if not (output / "compatibility.json").is_file():
            if output.exists():
                raise ValueError("retained failed compatibility attempt needs a fresh destination: " + name)
            process = subprocess.run(command, cwd=REPO, env=env, text=True,
                                     capture_output=True, timeout=600)
            (SCRATCH / ("compat-" + name + ".raw")).write_text(process.stdout + process.stderr)
            if process.returncode:
                print(process.stdout[-2000:], process.stderr[-2000:], file=sys.stderr)
                raise RuntimeError(f"compatibility failed for {name}: {process.returncode}")
        receipt = json.loads((output / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("case_id") != case_id:
            raise ValueError("exact compatibility proof missing: " + name)
        positive = HERE / ("cpu-compat-" + name + "-analysis.log")
        negative = HERE / ("cpu-compat-" + name + "-negative.log")
        clean_copy(output / "compatibility-analysis.log", positive)
        clean_copy(output / "negative-analysis.log", negative)
        if receipt["log_sha256"] != sha(positive) or receipt["negative_log_sha256"] != sha(negative):
            raise ValueError("clean returned logs differ from original proof: " + name)
        receipt_path = HERE / ("cpu-compat-" + name + "-receipt.json")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        entry["compatibility"] = {"command": " ".join(command), "log": positive.name,
                                  "negative_log": negative.name, "receipt": receipt_path.name,
                                  "sha256": sha(receipt_path)}
        entry["negative"] = {"log": negative.name,
                             "log_sha256": sha(negative)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                                   "source_env_var": "SCENARIO_SCHOOL_PASS_SITE_PACKET"}
        evidence = ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json",
                    "trace.jsonl", "capture/evidence.jsonl"]
        entry["acquisition"] = {
            channel["name"]: {"entrypoint": "native_capture.py",
                               "method": "source_bound_same_tick_native_readback",
                               "evidence": evidence}
            for channel in json.loads((HERE / entry["construction"]).read_text())["recording_description"]["channels"]
        }
        print(name, "positive and missing-source compatibility passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
