"""Bind measured synthetic physical outcomes and Native closure for each case."""
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
    manifest_path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.removeprefix(HERE.name + "__")
        fixtures = []
        lifecycle = None
        for kind in KINDS:
            result = HERE / "cases" / variant / ("physical-" + kind + ".json")
            log = HERE / "cases" / variant / ("proof-physical-" + kind + ".log")
            command = [sys.executable, str(HERE / "physical_probe.py"),
                       "--case", case_id, "--kind", kind, "--output", str(result)]
            completed = subprocess.run(command, cwd=REPO, env=os.environ.copy(), text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(completed.stdout.rstrip() + "\n")
            if completed.returncode:
                raise ValueError("physical probe failed: " + case_id + " " + kind +
                                 " " + completed.stdout[-1200:])
            summary = json.loads(completed.stdout)
            if kind == "complete_motion":
                lifecycle = {"events": summary["lifecycle"], "exit_code": 0,
                             "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                             "result": str(result.relative_to(HERE)),
                             "result_sha256": sha(result), "exit_code": 0})
        receipt = HERE / "cases" / variant / "physical-receipt.json"
        receipt.write_text(dump({"case_id": case_id,
                                 "construction_sha256": entry["construction_sha256"],
                                 "fixtures": fixtures, "lifecycle": lifecycle,
                                 "physical_acceptance_claimed": False}))
        entry["physical_preparation"] = {
            "receipt": str(receipt.relative_to(HERE)), "sha256": sha(receipt)}
        print(variant, "physical outcomes and owner closure passed", flush=True)
    manifest_path.write_text(dump(manifest))


if __name__ == "__main__":
    main()
