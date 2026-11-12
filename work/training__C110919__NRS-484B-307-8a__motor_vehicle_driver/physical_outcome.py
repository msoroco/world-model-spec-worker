"""Source-shaped maneuver completion gate for the red-signal right-turn cell.

CPU fixtures exercise branches only. A real caller must establish Native
provenance independently of these rows before this can report completion.
"""

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def check_lifecycle(events, native_exit_code):
    if events != EVENTS or native_exit_code != 0:
        raise ValueError("Saved processing started before Native owner release")
    return {"events": EVENTS, "exit_code": 0}


def classify(samples, geometry, *, provenance_kind, diagnostic_fixture):
    sources = ["native_samples.jsonl", "road_geometry.json"]
    method = "480 joined Native frame samples, full body, signal, conflict and destination exit"
    measured = None
    try:
        if len(samples) != 480 or geometry["signal_actor_id"] <= 0:
            raise ValueError("Missing full signal and motion evidence")
        if geometry["stop_line_y_m"] >= geometry["nearest_crosswalk_y_m"]:
            raise ValueError("Stop reference geometry differs")
        frames = [s["native_frame"] for s in samples]
        if any(b <= a for a, b in zip(frames, frames[1:])):
            raise ValueError("Native frame order differs")
        if any(s["signal_state_observed"] != "Red" for s in samples):
            raise ValueError("Steady red observation missing")
        last = samples[-1]["native_center_xy_m"]
        entered = [i for i, s in enumerate(samples)
                   if s["native_center_xy_m"][0] >= 8 and
                   s["native_center_xy_m"][1] > -7]
        occupied = [i for i, s in enumerate(samples)
                    if s["walker_conflict_occupied"] is True]
        if not entered or not occupied:
            raise ValueError("Conflict and turn samples missing")
        if any(len(s["native_body_xy_m"]) != 4 or s["speed_mps"] < 0
               for s in samples):
            raise ValueError("Full body or speed missing")
        measured = {"turn_entry_frame": frames[entered[0]],
                    "last_walker_conflict_frame": frames[occupied[-1]],
                    "destination_exit_observed": last[0] > 13 and abs(last[1] + 1.75) < 2,
                    "conflict_cleared_before_entry": occupied[-1] < entered[0]}
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    synthetic = any(isinstance(s, dict) and
                    (s.get("synthetic_diagnostic") is True or
                     s.get("speed_provenance") == "synthetic_native_sample")
                    for s in samples)
    original = provenance_kind == "native" and diagnostic_fixture is False and not synthetic
    if measured is None or not original:
        status = "unverified"
    elif measured["destination_exit_observed"] and measured["conflict_cleared_before_entry"]:
        status = "met"
    else:
        status = "not_met"
    return {"physical_checks": {"maneuver": {"status": status, "method": method,
                                             "sources": sources}},
            "maneuver_completed": status == "met",
            "realized_observables": measured if status == "met" else {},
            "source_shaped_motion": measured, "provenance_kind": provenance_kind,
            "diagnostic_fixture": diagnostic_fixture, "accepted": False,
            "legal_verdict_claimed": False}
