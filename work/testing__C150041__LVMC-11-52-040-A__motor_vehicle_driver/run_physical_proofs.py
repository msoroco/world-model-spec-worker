"""Bind exact synthetic physical CPU outcomes to the current six-case manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_lifecycle(events, exit_code):
    if events != EVENTS or exit_code != 0:
        raise ValueError("saved processing preceded complete Native ownership closure")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    scratch = (REPO / ".runtime-work").resolve()
    output = args.output_root.resolve()
    if not output.is_relative_to(scratch) or output.exists():
        raise ValueError("fresh physical proof root under .runtime-work required")
    output.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text())
    if {entry["case_id"] for entry in manifest["cases"]} != {
            ROOT.name + "__" + suffix for suffix in REQUESTS}:
        raise ValueError("six exact case identities required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        construction = ROOT / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("physical proof construction changed: " + suffix)
        fixtures = []
        folder = ROOT / "diagnostic" / suffix
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            history = output / suffix / kind / "history.jsonl"
            result_path = folder / ("physical-" + kind + "-result.json")
            log = folder / ("physical-" + kind + ".log")
            if result_path.exists() or log.exists():
                raise ValueError("physical proof outputs must be fresh")
            command = [sys.executable, str(ROOT / "physical_proof.py"),
                       "--case", suffix, "--kind", kind,
                       "--history", str(history), "--result", str(result_path)]
            run = subprocess.run(command, cwd=REPO, env=os.environ,
                                 capture_output=True, text=True, timeout=120)
            log.write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError("physical CPU proof failed: " + str(log))
            result = json.loads(result_path.read_text())
            if (result["case_id"] != entry["case_id"] or
                    result["physical_checks"]["maneuver"]["status"] != expected or
                    result["physical_acceptance_claimed"] is not False):
                raise ValueError("physical fixture status differs: " + suffix + kind)
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0,
                             "log": log.relative_to(ROOT).as_posix(),
                             "log_sha256": sha(log),
                             "result": result_path.relative_to(ROOT).as_posix(),
                             "result_sha256": sha(result_path)})
        verify_lifecycle(EVENTS, 0)
        for wrong_events, wrong_exit in ((EVENTS[:-2] + EVENTS[-1:] + EVENTS[-2:-1], 0),
                                         (EVENTS, 1)):
            try:
                verify_lifecycle(wrong_events, wrong_exit)
            except ValueError:
                pass
            else:
                raise ValueError("invalid ownership lifecycle accepted")
        life_log = folder / "physical-lifecycle.log"
        life_log.write_text(json.dumps({"scope": "synthetic CPU ordering protocol",
                                        "positive": EVENTS,
                                        "rejected": ["saved before owner release",
                                                     "nonzero Native exit"]}) + "\n")
        receipt = folder / "physical-preparation.json"
        receipt.write_text(json.dumps({
            "format": "worker-physical-preparation",
            "case_id": entry["case_id"],
            "construction_sha256": entry["construction_sha256"],
            "provenance_kind": "synthetic_fixture",
            "physical_acceptance_claimed": False,
            "fixtures": fixtures,
            "lifecycle": {"events": EVENTS, "exit_code": 0,
                          "log": life_log.relative_to(ROOT).as_posix(),
                          "log_sha256": sha(life_log)}}, indent=2) + "\n")
        entry["physical_preparation"] = {
            "receipt": receipt.relative_to(ROOT).as_posix(), "sha256": sha(receipt)}
        print(suffix, "three physical CPU outcomes and lifecycle passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
