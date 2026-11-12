"""CPU motion branch checks for two alley stop targets; no legal blockage claim."""

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def lifecycle(events, exit_code):
    if events != EVENTS or exit_code != 0:
        raise ValueError("Saved analysis preceded Native owner release")
    return {"events": EVENTS, "exit_code": 0}


def classify(rows, road, suffix, *, provenance_kind, diagnostic_fixture):
    target = {"reference": -12.0, "contrast": 0.0}[suffix]
    source = ["native_samples.jsonl", "road_geometry.json"]
    check = {"status": "unverified", "method": "480 ordered body/pose/velocity samples and 2 s terminal stop", "sources": source}
    observed = {}
    try:
        if len(rows) != 480 or road["alley_native_road_id"] <= 0:
            raise ValueError("Full alley motion source missing")
        frames = [r["native_frame"] for r in rows]
        if any(b <= a for a, b in zip(frames, frames[1:])):
            raise ValueError("Frame order differs")
        if any(len(r["native_body_xy_m"]) != 4 or r["speed_mps"] < 0 for r in rows):
            raise ValueError("Full body or speed missing")
        first, last = rows[0]["native_center_xy_m"], rows[-1]["native_center_xy_m"]
        if first[0] > -40 or abs(first[1] + 2) > 0.5:
            raise ValueError("Alley approach absent")
        for row in (rows[0], rows[-1]):
            body = row["native_body_xy_m"]
            center = row["native_center_xy_m"]
            if any(abs(sum(point[axis] for point in body) / 4 - center[axis]) > 0.2
                   for axis in (0, 1)):
                raise ValueError("Body and center disagree")
        parked = all(r["speed_mps"] <= 0.05 and
                     abs(r["native_center_xy_m"][0] - target) <= 0.5 for r in rows[-40:])
        observed = {"target_x_m": target, "terminal_xy_m": last,
                    "terminal_stop_frames": 40 if parked else 0,
                    "target_reached_and_parked": parked}
        synthetic = any(r.get("synthetic_diagnostic") is True or
                        r.get("speed_provenance") == "synthetic_native_sample" for r in rows)
        if provenance_kind == "native" and not diagnostic_fixture and not synthetic:
            check["status"] = "met" if parked else "not_met"
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return {"physical_checks": {"maneuver": check},
            "maneuver_completed": check["status"] == "met",
            "realized_observables": observed if check["status"] == "met" else {},
            "provenance_kind": provenance_kind, "diagnostic_fixture": diagnostic_fixture,
            "accepted": False, "legal_verdict_claimed": False,
            "alley_access_or_legal_blockage_verified": False}
