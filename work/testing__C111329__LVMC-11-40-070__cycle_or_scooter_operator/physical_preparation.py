"""CPU checks for physical outcome classification and Native owner ordering."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(case: dict, trace: dict | None) -> dict:
    if trace is None:
        status = "unverified"
        reason = "missing original or diagnostic motion evidence"
    else:
        rows = trace.get("samples", [])
        if len(rows) != 900 or trace.get("case_id") != case["case_id"]:
            raise ValueError("physical fixture lacks exact 900-frame source")
        crossed = rows[0]["bike_front_xy"][0] < 0 < rows[-1]["bike_front_xy"][0]
        held = rows[-1]["bike_front_xy"][0] < 0 and rows[-1]["bike_speed_mps"] == 0
        met = crossed if case["operator_motion"] == "cross_stop_line" else held
        status = "met" if met else "not_met"
        reason = "measured diagnostic route endpoint, stop-line side and final speed"
    return {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "case_id": case["case_id"], "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status, "method": reason,
                                            "sources": ["case-specific diagnostic instruction trace"]}},
            "realized_observables": ({"diagnostic_motion": {"value": 1,
                                   "unit": "diagnostic outcome", "method": reason}}
                                     if status == "met" else {})}


def lifecycle(events: list[str]) -> None:
    if events != EVENTS:
        raise ValueError("saved processing preceded Native owner closure")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((ROOT / "case-plan.json").read_text())
    case = next(row for row in plan["cases"] if row["case_id"] == args.case)
    if args.kind == "lifecycle":
        lifecycle(EVENTS)
        print("Native owner lifecycle passed", args.case)
        return
    suffix = case["case_id"].split("__")[-1]
    source = ROOT / "cases" / suffix / "diagnostic-instruction-trace.json"
    if args.kind == "missing_evidence":
        trace = None
    else:
        trace = json.loads(source.read_text())
        if args.kind == "incomplete_motion":
            for row in trace["samples"]:
                if case["operator_motion"] == "cross_stop_line":
                    row["bike_front_xy"] = [-1.0, 0.0]
                    row["bike_speed_mps"] = 0.0
                else:
                    row["bike_front_xy"] = [1.0, 0.0]
    result = classify(case, trace)
    if result["physical_checks"]["maneuver"]["status"] != {
            "complete_motion": "met", "incomplete_motion": "not_met",
            "missing_evidence": "unverified"}[args.kind]:
        raise ValueError("diagnostic physical outcome differs from selected test")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.kind, result["physical_checks"]["maneuver"]["status"], args.case,
          "diagnostic trace sha256", sha(source) if source.is_file() else "missing")


if __name__ == "__main__":
    main()
