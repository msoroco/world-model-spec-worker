"""Bind three measured synthetic physical outcomes and Native closure per exact case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("physical scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(HERE.name + "__")
        fixtures = []
        lifecycle = None
        for kind in KINDS:
            result = HERE / ("physical-" + variant + "-" + kind + ".json")
            log = HERE / ("cpu-physical-" + variant + "-" + kind + ".log")
            command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / "physical_probe.py"),
                       "--case", case_id, "--kind", kind, "--output", str(result)]
            completed = subprocess.run(command, cwd=REPO, env=os.environ.copy(), text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(completed.stdout.rstrip() + "\n")
            if completed.returncode:
                raise ValueError("physical probe failed: " + case_id + " " + kind + " " + completed.stdout[-800:])
            summary = json.loads(completed.stdout)
            if kind == "complete_motion":
                lifecycle = {"events": summary["lifecycle"], "exit_code": 0,
                             "log": log.name, "log_sha256": sha(log)}
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result), "exit_code": 0})
        receipt = HERE / ("physical-" + variant + "-receipt.json")
        receipt.write_text(dump({"case_id": case_id,
                                 "construction_sha256": entry["construction_sha256"],
                                 "fixtures": fixtures, "lifecycle": lifecycle,
                                 "physical_acceptance_claimed": False}))
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print(variant, "complete/not_met/unverified and ownership closure", flush=True)
    manifest_path.write_text(dump(manifest))


if __name__ == "__main__":
    main()
