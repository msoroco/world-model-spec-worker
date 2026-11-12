"""Physical outcome checker for the C110919 red-to-green right-turn pair.

CPU fixtures only exercise decisions. An original caller still needs independent
Native provenance and pixel review before using a physical result.
"""
import math

CASES = ("green_release_wait", "green_release_red_turn")
RED = ("Red", "TrafficLightState.Red")
GREEN = ("Green", "TrafficLightState.Green")


def classify(samples, geometry, case_suffix, *, provenance_kind, diagnostic_fixture):
    if case_suffix not in CASES:
        raise ValueError("Unknown green-release case")
    measured = None
    try:
        if len(samples) != 480 or geometry["signal_actor_id"] <= 0 or \
           geometry["stopping_reference_kind"] != "marked_stop_line" or \
           geometry["stopping_reference_y_m"] != geometry["stop_line_y_m"] or \
           geometry["stop_line_y_m"] != -14.0:
            raise ValueError("Original green-release source or marked line missing")
        frames = [row["native_frame"] for row in samples]
        if any(not isinstance(frame, int) for frame in frames) or \
           any(b <= a for a, b in zip(frames, frames[1:])):
            raise ValueError("Native frame sequence differs")
        if any(row["signal_state_observed"] not in RED for row in samples[:160]) or \
           any(row["signal_state_observed"] not in GREEN for row in samples[160:]):
            raise ValueError("Observed governing signal transition differs")
        if any(len(row["native_body_xy_m"]) != 4 or
               not isinstance(row["speed_mps"], (int, float)) or
               not math.isfinite(row["speed_mps"]) or row["speed_mps"] < 0
               for row in samples):
            raise ValueError("Original full-body or speed sample missing")
        fronts = [max(vertex[1] for vertex in row["native_body_xy_m"])
                  for row in samples]
        first_stop = next((i for i in range(160) if samples[i]["speed_mps"] <= .05
                           and fronts[i] < -14.0), None)
        crossing = next((i for i in range(1, 480)
                         if fronts[i-1] < -14.0 <= fronts[i]), None)
        entered = next((i for i, row in enumerate(samples)
                        if row["native_center_xy_m"][0] >= 8 and
                        row["native_center_xy_m"][1] > -7), None)
        occupied = [i for i, row in enumerate(samples)
                    if row["walker_conflict_occupied"] is True]
        if first_stop is None or crossing is None or entered is None or not occupied:
            raise ValueError("Halt, crossing, turn or pedestrian history absent")
        red_wait = crossing >= 160 and all(samples[i]["speed_mps"] <= .05 and
                                           fronts[i] < -14.0
                                           for i in range(first_stop, 160))
        longest = 0
        run = 0
        for i in range(crossing):
            run = run + 1 if samples[i]["speed_mps"] <= .05 and fronts[i] < -14.0 else 0
            longest = max(longest, run)
        last = samples[-1]["native_center_xy_m"]
        measured = {"first_stationary_frame": frames[first_stop],
                    "first_front_crossing_frame": frames[crossing],
                    "first_green_frame": frames[160],
                    "remain_stopped_until_green": red_wait,
                    "halt_before_line": longest >= 10,
                    "stationary_pre_crossing_frames": longest,
                    "turn_entry_frame": frames[entered],
                    "conflict_cleared_before_turn_entry": occupied[-1] < entered,
                    "destination_exit_observed": last[0] > 13 and abs(last[1] + 1.75) < 2}
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    synthetic = any(isinstance(row, dict) and
                    (row.get("synthetic_diagnostic") is True or
                     row.get("speed_provenance") == "synthetic_native_sample")
                    for row in samples)
    original = provenance_kind == "native" and diagnostic_fixture is False and \
               not synthetic and geometry.get("synthetic_diagnostic") is not True
    if measured is None or not original:
        status = "unverified"
    elif (measured["halt_before_line"] and measured["conflict_cleared_before_turn_entry"]
          and measured["destination_exit_observed"] and
          measured["remain_stopped_until_green"] == (case_suffix == "green_release_wait")):
        status = "met"
    else:
        status = "not_met"
    return {"physical_checks": {"green_release_right_turn": {
                "status": status,
                "method": "480 original full-body, speed, signal and walker samples",
                "sources": ["native_samples.jsonl", "road_geometry.json"]}},
            "maneuver_completed": status == "met",
            "source_shaped_motion": measured,
            "realized_observables": measured if status == "met" else {},
            "provenance_kind": provenance_kind,
            "diagnostic_fixture": diagnostic_fixture,
            "accepted": False, "legal_verdict_claimed": False}
