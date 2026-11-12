"""Classify a selected maneuver from retained frame samples.

This is a CPU checker. The caller supplies provenance established by the
capture seal; diagnostic samples never establish physical completion.
"""
from physical_motion_audit import EXPECTED, measure_rows


def classify(samples, survey, suffix, context, *, provenance_kind, diagnostic_fixture):
    if suffix not in EXPECTED:
        raise ValueError("Unknown selected physical maneuver")
    sources = ["native_samples.jsonl", "road_geometry.json",
               "context.json" if suffix.startswith("traversal_") else
               "statutory_context.json"]
    try:
        measured = measure_rows(samples, survey, suffix, context,
                                enforce_target=False)
    except (ValueError, KeyError, TypeError):
        measured = None
    synthetic_rows = any(row.get("synthetic_diagnostic") is True or
                         row.get("speed_provenance") == "synthetic_native_sample"
                         for row in samples if isinstance(row, dict))
    original = (provenance_kind == "native" and diagnostic_fixture is False and
                not synthetic_rows)
    if measured is None or not original:
        status = "unverified"
    elif measured["observed_relation"] == EXPECTED[suffix] and measured["endpoint_parked"]:
        status = "met"
    else:
        status = "not_met"
    return {
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "joined 480-frame full-body, speed, road and endpoint measurement",
            "sources": sources}},
        "maneuver_completed": status == "met",
        "realized_observables": (measured["measured"] if status == "met" else {}),
        "provenance_kind": provenance_kind,
        "diagnostic_fixture": diagnostic_fixture,
        "source_shaped_motion": measured,
        "accepted": False,
        "legal_verdict_claimed": False,
    }


def check_lifecycle(events, *, native_exit_code):
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected or native_exit_code != 0:
        raise ValueError("Saved processing started before Native ownership closure")
    return {"events": expected, "exit_code": 0}
