"""Source-shaped CPU physical and owner-lifecycle fixtures for roundabout entry."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from gap_request import request_row

ASSIGNMENT = "training__C239014__LVMC-11-43-010-B__motor_vehicle_driver"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def fixture(condition, kind):
    if condition not in ("condition_a", "condition_b") or kind not in (
            "complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown physical fixture")
    rows = [request_row(i, "waited_entry" if condition == "condition_a" else
                        "early_entry") for i in range(600)]
    if kind == "missing_evidence":
        rows.pop(300)
    elif kind == "incomplete_motion":
        for row in rows:
            row["ego"]["phase"] = "entry_wait"
    if len(rows) != 600:
        status, completed, observables = "unverified", False, {}
    else:
        entries = [i for i, row in enumerate(rows)
                   if row["ego"]["phase"] == "circulation"]
        completed = bool(entries)
        status = "met" if completed else "not_met"
        observables = {"first_authored_ring_entry_frame": entries[0] if entries else None,
                       "source_frames": len(rows)}
    return {"format": "c239014-cpu-physical-fixture-v1",
            "case_id": ASSIGNMENT + "__selected_a60a4f45__" + condition,
            "kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600-frame authored request continuity and ring-entry phase; original Native realization pending",
                "sources": ["gap_request.py", "native-raw-actors.jsonl",
                            "roundabout-map-readback.json"]}},
            "maneuver_completed": completed, "realized_observables": observables,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        if EVENTS.index("owner_released") >= EVENTS.index("saved_processing_started"):
            raise ValueError("Saved processing precedes owner release")
        value = {"format": "c239014-cpu-lifecycle-v1", "events": EVENTS,
                 "provenance_kind": "synthetic_fixture", "original_native_executed": False}
    else:
        value = fixture(args.condition, args.kind)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Physical fixture status differs")
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "kind": args.kind,
                      "condition": args.condition,
                      "physical_or_legal_acceptance": False}, sort_keys=True))


if __name__ == "__main__":
    main()
