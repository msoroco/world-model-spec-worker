"""Reconstruct diagnostic passing motion and lifecycle ordering from CPU rows."""

import argparse
import hashlib
import json


def motion(case_id, kind):
    rows = []
    for frame in range(600 if kind != "missing_evidence" else 599):
        rows.append({"frame": frame, "time_s": frame / 20,
                     "ego_x_m": -20 + (0.1 * frame if kind == "complete_motion" else 0),
                     "cycle_x_m": 0.05 * frame,
                     "ego_lane": "left" if case_id.endswith("witness_1") and frame >= 260 else "right"})
    source_bytes = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(rows) != 600:
        status = "unverified"
        overlapping = []
    else:
        relative = [row["ego_x_m"] - row["cycle_x_m"] for row in rows]
        overlapping = [row["frame"] for row, separation in zip(rows, relative) if abs(separation) <= 4]
        status = "met" if overlapping and relative[0] < -4 and relative[-1] > 4 else "not_met"
    result = {
        "case_id": case_id, "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "maneuver_completed": status == "met",
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "20 Hz joined subject and cyclist longitudinal pose; body-overlap span and before/after order",
            "sources": [{"name": "synthetic-actor-rows", "sha256": hashlib.sha256(source_bytes).hexdigest(),
                         "rows": len(rows)}],
            "first_overlap_frame": overlapping[0] if overlapping else None,
            "last_overlap_frame": overlapping[-1] if overlapping else None,
        }},
        "realized_observables": ({"passing_span_frames": {"value": len(overlapping), "unit": "frames",
                                                         "source": "synthetic-actor-rows"}} if status == "met" else {}),
        "original_native_observed": False, "legal_judgment": None,
    }
    return result


def lifecycle():
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    required = {"encoders_closed": "capture_finished",
                "restoration_verified": "encoders_closed",
                "native_exit": "restoration_verified",
                "owner_released": "native_exit",
                "saved_processing_started": "owner_released"}
    seen = set()
    for event in events:
        if event in required and required[event] not in seen:
            raise ValueError("Saved processing can start only after ownership closure")
        seen.add(event)
    return {"events": events, "exit_code": 0, "scope": "CPU lifecycle order only"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"), required=True)
    args = parser.parse_args()
    if "__" not in args.case or not args.case.startswith("training__C247014__NRS-484B-270-2a__motor_vehicle_driver__"):
        raise ValueError("Another exact case selected")
    print(json.dumps(lifecycle() if args.kind == "lifecycle" else motion(args.case, args.kind),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
