"""CPU branch test for route completion; capture provenance is checked separately."""

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def check_lifecycle(events, native_exit_code):
    if events != EVENTS or native_exit_code != 0:
        raise ValueError("Saved processing began before Native ownership closed")
    return {"events": EVENTS, "exit_code": 0}


def classify(rows, road, *, provenance_kind, diagnostic_fixture):
    sources = ["native_samples.jsonl", "road_geometry.json"]
    check = {"status": "unverified", "method": "joined 480 ordered frame samples, full body and destination exit", "sources": sources}
    measured = {}
    try:
        if len(rows) != 480 or not road.get("native_map_sha256"):
            raise ValueError("Incomplete Native frame or map readback")
        frames = [row["native_frame"] for row in rows]
        if any(b <= a for a, b in zip(frames, frames[1:])):
            raise ValueError("Frames out of order")
        if any(len(row["native_body_xy_m"]) != 4 or row["speed_mps"] < 0 for row in rows):
            raise ValueError("Body or speed absent")
        first = rows[0]["native_center_xy_m"]
        last = rows[-1]["native_center_xy_m"]
        for sample, center in ((rows[0], first), (rows[-1], last)):
            body = sample["native_body_xy_m"]
            if any(abs(sum(point[axis] for point in body) / 4 - center[axis]) > 0.2
                   for axis in (0, 1)):
                raise ValueError("Center and body readback differ")
        entered = [row["native_frame"] for row in rows if row["native_center_xy_m"][0] > 10]
        reference_y = road.get("stop_line_y_m")
        if reference_y is None:
            reference_y = road["stopping_reference_y_m"]
        if not entered or first[1] >= reference_y:
            raise ValueError("Approach or turn entry absent")
        measured = {"approach_frame": frames[0], "turn_entry_frame": entered[0],
                    "final_frame": frames[-1], "destination_xy_m": last,
                    "destination_exit_observed": last[0] > 20 and -5 < last[1] < 1}
        synthetic = any(row.get("synthetic_diagnostic") is True or
                        row.get("speed_provenance") == "synthetic_native_sample" for row in rows)
        if provenance_kind == "native" and not diagnostic_fixture and not synthetic:
            check["status"] = "met" if measured["destination_exit_observed"] else "not_met"
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return {"physical_checks": {"maneuver": check},
            "maneuver_completed": check["status"] == "met",
            "realized_observables": measured if check["status"] == "met" else {},
            "provenance_kind": provenance_kind, "diagnostic_fixture": diagnostic_fixture,
            "accepted": False, "legal_verdict_claimed": False}
