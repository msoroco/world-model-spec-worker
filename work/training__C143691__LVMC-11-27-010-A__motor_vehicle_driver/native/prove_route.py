"""Deterministic requested-route tests; not a physical Native run."""

import hashlib
import json
from pathlib import Path

from route import FRAMES, check_scene, target


def reject(label, scene, expected):
    try:
        check_scene(scene)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    scene = {"barrier_x_m": 8.0, "barrier_clear_gap_m": 3.2,
             "vehicle_width_m": 1.9, "trail_lateral_bounds_m": [-2.0, 2.0]}
    check_scene(scene)
    outside = [target("outside", frame) for frame in range(FRAMES)]
    within = [target("within", frame) for frame in range(FRAMES)]
    assert all(a["x_m"] == b["x_m"] and a["target_speed_mps"] == b["target_speed_mps"]
               for a, b in zip(outside, within))
    assert all(a["y_m"] == 6.0 and b["y_m"] == 0.0 for a, b in zip(outside, within))
    assert outside[290]["x_m"] == within[290]["x_m"] == 8.0
    negative = [reject("blocked_gap", {**scene, "barrier_clear_gap_m": 1.0}, "vehicle clearance"),
                reject("shifted_barrier", {**scene, "barrier_x_m": 10.0}, "Barrier location"),
                reject("changed_trail_bounds", {**scene, "trail_lateral_bounds_m": [-1.0, 1.0]}, "Trail boundary")]
    proof = {"format": "worker-cpu-trail-route-proof", "passed": True,
             "diagnostic_only": True, "physical_result": "unobserved",
             "frame_count": FRAMES, "shared_speed_mps": 4.0,
             "comparison_variable": "requested_lateral_route", "negative": negative}
    path = Path(__file__).with_name("route-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
