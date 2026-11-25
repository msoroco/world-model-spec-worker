"""Build case-bound CPU counterfactuals for physical status and lifecycle gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from native_construction import ASSIGNMENT


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VARIANTS = ("accepted_source_1", "accepted_source_2", "accepted_source_3",
            "both_observed", "signal_missing", "check_missing")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build(variant, attempt):
    case = ASSIGNMENT + "__" + variant
    folder = HERE / "cases" / variant
    base = json.loads((Path(attempt) / "result.json").read_text())
    if base.get("case_id") != case or base.get("maneuver_completed") is not True:
        raise ValueError("passing diagnostic result for exact case required")
    base.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True,
                physical_acceptance_claimed=False, legal_acceptance_claimed=False)
    rows = []
    for kind, status in (("complete_motion", "met"),
                         ("incomplete_motion", "not_met"),
                         ("missing_evidence", "unverified")):
        value = json.loads(json.dumps(base))
        if status != "met":
            value["maneuver_completed"] = False
            value["realized_observables"] = {}
            value["physical_checks"]["maneuver"] = {
                "status": status,
                "method": ("synthetic_destination_offset_counterfactual" if
                           status == "not_met" else "synthetic_missing_pose_counterfactual"),
                "sources": {"fixture_condition": kind}}
        result = folder / "physical-fixtures" / (kind + ".json")
        write(result, value)
        log = folder / "physical-fixtures" / (kind + ".log")
        command = (f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python "
                   f"work/{ASSIGNMENT}/physical_fixture_check.py --case {case} "
                   f"--expected {status} --result {result.relative_to(REPO)}")
        run = subprocess.run([sys.executable, str(HERE / "physical_fixture_check.py"),
                              "--case", case, "--expected", status,
                              "--result", str(result)], capture_output=True, text=True)
        log.write_text(run.stdout + run.stderr)
        if run.returncode:
            raise ValueError("synthetic physical fixture check failed: " + kind)
        rows.append({"kind": kind, "command": command,
                     "exit_code": run.returncode,
                     "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                     "result": str(result.relative_to(HERE)),
                     "result_sha256": sha(result)})
    life = folder / "physical-fixtures" / "lifecycle.json"
    write(life, {"events": ["capture_finished", "encoders_closed",
             "restoration_verified", "native_exit", "owner_released",
             "saved_processing_started"], "diagnostic_fixture": True})
    life_log = folder / "physical-fixtures" / "lifecycle.log"
    run = subprocess.run([sys.executable, str(HERE / "physical_fixture_check.py"),
                          "--lifecycle", str(life)], capture_output=True, text=True)
    life_log.write_text(run.stdout + run.stderr)
    if run.returncode:
        raise ValueError("synthetic lifecycle check failed")
    construction = folder / "construction.json"
    proof = {"format": "worker-physical-preparation",
             "case_id": case, "construction_sha256": sha(construction),
             "fixtures": rows, "lifecycle": {"events": json.loads(life.read_text())["events"],
                 "exit_code": run.returncode, "log": str(life_log.relative_to(HERE)),
                 "log_sha256": sha(life_log)}}
    receipt = folder / "physical-preparation.json"
    write(receipt, proof)
    return receipt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    print(build(args.variant, args.attempt))
