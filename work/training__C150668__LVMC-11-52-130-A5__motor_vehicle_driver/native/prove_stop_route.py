"""CPU-only stop policy tests; fixture traces are not CARLA motion."""

import copy
import hashlib
import json
from pathlib import Path

from stop_route import FRAMES, STOP_X_M, command, validate_observed


def fixture(case):
    station = STOP_X_M[case]
    return [{"video_frame": i, "time_s": i / 20,
             "observed_x_m": -50 + (station + 50) * i / 100 if i < 100 else station,
             "observed_speed_mps": 3.0 if i < 100 else 0.0} for i in range(FRAMES)]


def reject(label, case, rows, expected):
    try:
        validate_observed(case, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    outside, band = fixture("outside"), fixture("side_band")
    positive = [validate_observed("outside", outside), validate_observed("side_band", band)]
    assert command("outside", 0, -50, 3)["phase"] == "approach"
    assert command("side_band", 100, 5, 0)["phase"] == "hold"
    bad = copy.deepcopy(band)
    bad[250]["observed_speed_mps"] = 1.0
    negative = [reject("moving_during_stop", "side_band", bad, "continuously observed"),
                reject("wrong_station", "side_band", outside, "overshot requested stop"),
                reject("short_trace", "side_band", band[:-1], "incomplete 30-second")]
    proof = {"format": "worker-cpu-sidewalk-fixture-stop-route-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("stop-route-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
