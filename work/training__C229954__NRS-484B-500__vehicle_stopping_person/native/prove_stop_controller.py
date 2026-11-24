"""Positive and negative diagnostic for the destination-stop policy."""

import json

from stop_controller import FRAMES, command, prove_trace


def rejected(rows, mutation, expected):
    copy = [dict(row) for row in rows]
    mutation(copy)
    try:
        prove_trace(copy)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError("Negative trace accepted")


def main():
    rows = [{"native_frame": i, "time_s": i / 20,
             "remaining_route_m": max(0.0, 100 - i) * 0.05,
             "observed_speed_mps": 1.0 if i < 100 else 0.0} for i in range(FRAMES)]
    proof = prove_trace(rows)
    assert command(0, 10.0, 1.0)["phase"] == "approach"
    assert command(80, 0.8, 1.0)["phase"] == "brake"
    assert command(100, 0.0, 0.0)["phase"] == "hold"
    negatives = {
        "incomplete": rejected(rows, lambda r: r.pop(), "Incomplete"),
        "bad_join": rejected(rows, lambda r: r[50].__setitem__("native_frame", 51), "frame/time join"),
        "moving_after_stop": rejected(rows, lambda r: r[200].__setitem__("observed_speed_mps", 1.0), "Continuous destination rest"),
        "overshoot": rejected(rows, lambda r: r[20].__setitem__("remaining_route_m", -2.0), "overshoot"),
    }
    print(json.dumps({"format": "worker-stop-controller-synthetic-proof", "positive": proof,
                      "negative_rejections": negatives, "physical_execution": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
