"""CPU stub executes original-frame body/ray/exception acquisition calls."""

from frame_capture import capture_frame
from prove_rail_native_rays import Actor, Location, World, review


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


ego = Actor(1, 0)
ego.pose.location.x = -2
ego.get_velocity = lambda: Location(6, 0, 0)
left, right = Actor(2, -70), Actor(3, 70)
actors = [{"side": "left", "actor": left}, {"side": "right", "actor": right}]
reviews = {"railway": review,
           "approach": {"approach_direction_xy": [1, 0]}}
flagman = {"frame": 42, "source_ref": "native:flagman-duty", "on_duty": False}
signal = {"frame": 42, "source_ref": "native:signal-state", "installed": False,
          "visible": False, "indicates_approach": False}
world = World()
packet = capture_frame(world, ego, actors, reviews, Location, 42, flagman, signal)
assert packet["joined"]["speed_mps"] == 6
assert packet["joined"]["distance_to_crossing_m"] > 0
assert packet["joined"]["rail_left_clear_distance_m"] <= 50
assert packet["physical_acceptance_claimed"] is False
reject(lambda: capture_frame(world, ego, actors, reviews, Location, 43, flagman, signal),
       "flagman frame")
reject(lambda: capture_frame(world, ego, actors, reviews, Location, 42,
                             dict(flagman, source_ref=""), signal), "flagman frame")
print("PASS: original Native frame body, dynamic rays and exception-source join")
