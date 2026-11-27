"""Prove speed commands and invalid original readback rejection."""

from controller import control
from rail_sight import FIFTEEN_MPH_MPS


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


slow = control(0, 0, "slower_traversal")
at = control(0, 0, "at_limit_traversal")
fast = control(0, 0, "faster_traversal")
assert slow["requested_speed_mps"] < FIFTEEN_MPH_MPS < fast["requested_speed_mps"]
assert at["requested_speed_mps"] == FIFTEEN_MPH_MPS
assert slow["throttle"] > 0 and fast["throttle"] > 0
assert control(100, 10, "slower_traversal")["brake"] > 0
assert control(100, 6, "slower_traversal")["physical_target_met"] is None
assert control(100, 6, "slower_traversal", gain=1.25)["throttle"] > 0
reject(lambda: control(600, 6, "slower_traversal"), "600-frame")
reject(lambda: control(20, float("nan"), "slower_traversal"), "measured speed")
reject(lambda: control(20, 6, "slower_traversal", gain=3), "feedback gain")
print("PASS: original-speed feedback controls for 15-mph slow/fast crossing contrast")
