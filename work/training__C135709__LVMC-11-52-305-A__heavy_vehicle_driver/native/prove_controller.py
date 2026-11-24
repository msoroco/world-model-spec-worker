"""Source-shaped CPU controller checks; never evidence of CARLA motion."""

import copy
import hashlib
import json
from pathlib import Path

from controller import STATIONS_M, TOTAL_FRAMES, command, validate_observed_completion


def fixture(case):
    station = STATIONS_M[case]
    return [{"video_frame": i, "time_s": i / 20,
             "observed_x_m": -80 + (station + 80) * i / 100 if i < 100 else station,
             "observed_speed_mps": 3.0 if i < 100 else 0.0}
            for i in range(TOTAL_FRAMES)]


def reject(label, case, rows, text):
    try:
        validate_observed_completion(case, rows)
    except ValueError as error:
        assert text in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    away = fixture("away")
    beside = fixture("beside")
    positive = [validate_observed_completion("away", away),
                validate_observed_completion("beside", beside)]
    assert command("away", 0, -80, 3)["phase"] == "approach"
    assert command("beside", 95, 39, 3)["phase"] == "brake"
    assert command("beside", 100, 40, 0)["phase"] == "hold"
    bad = copy.deepcopy(beside)
    bad[300]["observed_speed_mps"] = 2.0
    negative = [reject("moving_during_park", "beside", bad, "continuously held"),
                reject("wrong_frontage", "beside", away, "continuously held"),
                reject("short_trace", "beside", beside[:-1], "incomplete 30-second")]
    proof = {"format": "worker-cpu-parking-controller-proof", "passed": True,
             "diagnostic_only": True, "fixtures_are_original_native": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("controller-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
