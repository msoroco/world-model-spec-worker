"""CPU-only rail controller diagnostics; never original CARLA motion."""

import copy
import hashlib
import json
from pathlib import Path

from controller import FRAMES, TARGET_CENTER_X_M, command, validate_observed


def fixture(case):
    stop = TARGET_CENTER_X_M[case]
    return [{"video_frame": i, "time_s": i / 20,
             "vehicle_center_x_m": -10 + (stop + 10) * i / 100 if i < 100 else stop,
             "observed_speed_mps": (stop + 10) / 5 if i < 100 else 0.0}
            for i in range(FRAMES)]


def reject(label, case, rows, expected):
    try:
        validate_observed(case, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    clear, short = fixture("clear"), fixture("space_short")
    positive = [validate_observed("clear", clear), validate_observed("space_short", short)]
    assert command("clear", 0, -10, 5.4)["phase"] == "approach"
    assert command("space_short", 100, 14, 0)["phase"] == "hold"
    bad = copy.deepcopy(short)
    bad[250]["observed_speed_mps"] = 2.0
    negative = [reject("moving_after_stop", "space_short", bad, "not observed"),
                reject("wrong_target", "clear", short, "not observed"),
                reject("short_trace", "clear", clear[:-1], "incomplete 30-second")]
    proof = {"format": "worker-cpu-rail-controller-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("controller-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
