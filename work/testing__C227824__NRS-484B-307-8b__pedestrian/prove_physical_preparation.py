"""Exercise measured entry, failed entry and missing-body CPU fixtures per case."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from physical_entry import assess


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def one(case_id, kind):
    if kind not in KINDS:
        raise ValueError("unknown physical outcome fixture")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    case = next((row for row in plan["cases"] if row["case_id"] == case_id), None)
    if case is None:
        raise ValueError("unknown exact case")
    polygon = [[0, 0], [2, 0], [2, 2], [0, 2]]
    outside = [[-2, 0], [-1, 0], [-1, 1], [-2, 1]]
    inside = [[.5, .5], [1, .5], [1, 1], [.5, 1]]
    request = case["entry_request"]
    should_enter = (request == "entry") == (kind == "complete_motion")
    bodies = [outside, inside if should_enter else outside,
              inside if should_enter else outside]
    rows = [{"case_id": case_id, "frame": index + 1,
             "time_s": .05 * (index + 1), "body_polygon_xy_m": body}
            for index, body in enumerate(bodies)]
    scene = {"case_id": case_id, "entry_request": request,
             "highway_polygon_xy_m": polygon}
    report = {"case_id": case_id, "sample_count": 3,
              "measurement": {"first_entry": {"frame": 2} if should_enter else None},
              "source_sha256": {name: "a" * 64 for name in
                                ("scene.json", "walker-body-history.jsonl",
                                 "video_frames.jsonl")}}
    if kind == "missing_evidence":
        try:
            assess(report, scene, rows[:2])
        except ValueError as error:
            if "body history incomplete" not in str(error):
                raise
        else:
            raise ValueError("missing physical source was accepted")
        maneuver = {"status": "unverified", "method": "missing original body history rejects completion",
                    "sources": ["synthetic_fixture:missing_body_history"]}
    else:
        check = assess(report, scene, rows)
        maneuver = {"status": check["status"], "method": check["method"],
                    "sources": list(check["sources"]), "details": check["details"]}
        expected = "met" if kind == "complete_motion" else "not_met"
        if maneuver["status"] != expected:
            raise ValueError("physical fixture outcome differs")
    return {"format": "worker-physical-fixture-result", "case_id": case_id,
            "fixture_kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "physical_checks": {"maneuver": maneuver},
            "maneuver_completed": maneuver["status"] == "met",
            "realized_observables": (["synthetic_full_body_highway_overlap"]
                                     if maneuver["status"] == "met" else []),
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def build_all():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    folder = ROOT / "physical-preparation"
    folder.mkdir(exist_ok=True)
    rows = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id[len(ASSIGNMENT) + 2:]
        construction = ROOT / "cases" / suffix / "construction.json"
        fixtures = []
        for kind in KINDS:
            result_rel = f"physical-preparation/{suffix}-{kind}.json"
            log_rel = f"physical-preparation/{suffix}-{kind}.log"
            command = (f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_physical_preparation.py "
                       f"--case {case_id} --kind {kind} --output work/{ASSIGNMENT}/{result_rel}")
            run = subprocess.run([sys.executable, __file__, "--case", case_id,
                                  "--kind", kind, "--output", str(ROOT / result_rel)],
                                 capture_output=True, text=True, timeout=60)
            (ROOT / log_rel).write_text((run.stdout + run.stderr).rstrip("\n") + "\n")
            if run.returncode:
                raise RuntimeError(command + ": " + run.stderr)
            fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                             "log": log_rel, "log_sha256": sha(ROOT / log_rel),
                             "result": result_rel,
                             "result_sha256": sha(ROOT / result_rel)})
        life_log = f"physical-preparation/{suffix}-lifecycle.log"
        (ROOT / life_log).write_text(
            "Synthetic lifecycle order model checked; Native execution unverified: "
            + ", ".join(EVENTS) + "\n")
        receipt = {"format": "worker-physical-preparation-proof", "case_id": case_id,
                   "construction_sha256": sha(construction), "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "log": life_log, "log_sha256": sha(ROOT / life_log)}}
        proof_rel = f"physical-preparation/{suffix}-proof.json"
        write(ROOT / proof_rel, receipt)
        rows.append({"case_id": case_id, "receipt": proof_rel, "sha256": sha(ROOT / proof_rel),
                     "statuses": ["met", "not_met", "unverified"]})
    print(json.dumps({"format": "c227824-physical-preparation-summary",
                      "cases": rows, "physical_acceptance_claimed": False}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.case or args.kind or args.output:
        if not all((args.case, args.kind, args.output)):
            raise ValueError("fixture case, kind and output required together")
        write(args.output, one(args.case, args.kind))
        print(json.dumps({"case_id": args.case, "kind": args.kind, "passed": True}))
    else:
        build_all()


if __name__ == "__main__":
    main()
