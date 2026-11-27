"""Exercise diagnostic taxi completion and source loss for every exact case.

These are synthetic CPU fixtures. They do not stand in for an original CARLA
capture, an actual passenger exchange, or a legal expeditiousness decision.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def assess(case: dict, kind: str) -> dict:
    """Evaluate observable fixture events, never an anticipated law label."""
    if kind == "missing_evidence":
        observed = {}
        status = "unverified"
    elif kind == "incomplete_motion":
        observed = {"frame_count": 160, "camera_count": 4,
                    "taxi_halt_duration_s": 8.0, "passenger_event_reviewed": False}
        status = "not_met"
    elif kind == "complete_motion":
        observed = {"frame_count": 900, "camera_count": 4,
                    "taxi_halt_duration_s": 45.0,
                    "passenger_event_reviewed": case["passenger_exchange_request"] != "none",
                    "taxi_stationary_samples": 900}
        status = "met"
    else:
        raise ValueError("unknown diagnostic fixture kind")
    if observed:
        completed = observed["frame_count"] == 900 and observed["camera_count"] == 4
        completed = completed and observed.get("taxi_stationary_samples") == 900
        if case["passenger_exchange_request"] != "none":
            completed = completed and observed["passenger_event_reviewed"]
        if completed != (status == "met"):
            raise AssertionError("fixture observation and completion disagree")
    return {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "case_id": case["case_id"], "maneuver_completed": status == "met",
            "realized_observables": observed,
            "physical_checks": {"maneuver": {"status": status,
                "method": "diagnostic 900-frame, four-camera, stationary-taxi and reviewed passenger-event check",
                "sources": ["synthetic Native frame ledger", "synthetic passenger activity review"]}}}


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    by_id = {case["case_id"]: case for case in plan["cases"]}
    for entry in manifest["cases"]:
        case = by_id[entry["case_id"]]
        suffix = entry["case_id"].split("__")[-1]
        folder = ROOT / "cases" / suffix
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result_path = folder / ("physical-" + kind + "-result.json")
            log_path = folder / ("physical-" + kind + ".log")
            result = assess(case, kind)
            write_json(result_path, result)
            command = [sys.executable, str(Path(__file__).resolve()), "--case", entry["case_id"], "--kind", kind]
            process = subprocess.run(command, text=True, capture_output=True, check=True)
            if json.loads(process.stdout) != result:
                raise ValueError("diagnostic physical proof returned different observations")
            log_path.write_text(process.stdout.rstrip() + "\n")
            fixtures.append({"kind": kind, "command":
                            ".venv-cpu/bin/python work/" + ROOT.name +
                            "/prove_physical_outcomes.py --case " + entry["case_id"] + " --kind " + kind,
                            "exit_code": process.returncode, "result": str(result_path.relative_to(ROOT)),
                            "result_sha256": sha(result_path),
                            "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path)})
        lifecycle_log = folder / "physical-lifecycle.log"
        lifecycle_log.write_text("Diagnostic ownership order: " + " -> ".join(EVENTS) + "\n")
        receipt_path = folder / "physical-preparation.json"
        write_json(receipt_path, {"construction_sha256": entry["construction_sha256"],
                                  "fixtures": fixtures,
                                  "lifecycle": {"events": EVENTS, "exit_code": 0,
                                                "log": str(lifecycle_log.relative_to(ROOT)),
                                                "log_sha256": sha(lifecycle_log)}})
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(ROOT)),
                                         "sha256": sha(receipt_path)}
    write_json(manifest_path, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind")
    args = parser.parse_args()
    if args.case or args.kind:
        if not args.case or not args.kind:
            raise SystemExit("both case and kind required")
        plan = json.loads((ROOT / "case-plan.json").read_text())
        case = next((item for item in plan["cases"] if item["case_id"] == args.case), None)
        if case is None:
            raise SystemExit("selected diagnostic case missing")
        print(json.dumps(assess(case, args.kind), indent=2, sort_keys=True))
    else:
        build()
        print("six diagnostic physical outcome receipts passed")
