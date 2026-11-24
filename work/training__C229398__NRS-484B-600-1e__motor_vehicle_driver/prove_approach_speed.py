"""CPU measurement proof for above/at/below 80 mph in approach-only frames."""
import hashlib
import json
from pathlib import Path
from approach_speed_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def enc(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sample(mph):
    scope = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
             "cell_layout": "road", "cell_maneuver": "park", "cell_control": "curb",
             "approach_phase_source_id": "synthetic-phase-plan", "curb_parking_source_id": "synthetic-curb-plan"}
    mps = mph / 2.2369362920544
    frames = []
    for i in range(600):
        phase = "approach_driving" if i < 250 else "curb_parking" if i < 400 else "parked"
        v = mps if 100 <= i < 200 else 5.0 if phase == "approach_driving" else 0.0
        frames.append({"frame": i, "t_s": i / 20, "vehicle_id": "ego", "phase": phase,
                       "velocity_xyz_mps": [v, 0.0, 0.0], "requested_speed_mph": mph})
    return {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
            "vehicle_id": "ego", "frames": frames}, scope


def reject(packet, scope, expected):
    try:
        measure(enc(packet), enc(scope))
    except ValueError as exc:
        if str(exc) != expected:
            raise
        return
    raise RuntimeError("invalid source accepted")


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    require(hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA,
            "assignment source changed")
    require(hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA,
            "witness source changed")
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    require("greater than 80 miles per hour" in law, "statutory boundary changed")
    above, scope = sample(85.0)
    p = measure(enc(above), enc(scope))
    require(p["duration_s"] == 30 and p["approach_frames_above_80_mph"] == list(range(100, 200)),
            "above-boundary measurement failed")
    require(p["max_parked_speed_mph"] == 0 and not p["requested_speed_used"]
            and not p["cell_approach_scope_verified"], "parked/request distinction failed")
    at, scope = sample(80.0)
    q = measure(enc(at), enc(scope))
    require(q["approach_frames_above_80_mph"] == [], "at-boundary measurement failed")
    below, scope = sample(75.0)
    s = measure(enc(below), enc(scope))
    require(s["approach_frames_above_80_mph"] == [], "below-boundary measurement failed")
    scope["approach_phase_source_id"] = ""
    reject(below, scope, "temporal scope source missing")
    broken, scope = sample(85.0)
    broken["frames"][120]["velocity_xyz_mps"] = []
    reject(broken, scope, "native velocity source missing")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA,
                      "above_source_sha256": p["frame_sha256"], "at_source_sha256": q["frame_sha256"],
                      "below_source_sha256": s["frame_sha256"],
                      "checks": ["600_frame_30s_20hz", "measured_approach_above_at_below_80", "parked_phase_excluded", "requested_speed_ignored", "scope_source_rejection", "velocity_source_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
