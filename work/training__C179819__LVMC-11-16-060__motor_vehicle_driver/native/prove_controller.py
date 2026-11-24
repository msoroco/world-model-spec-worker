"""CPU-only speed-controller diagnostics, not original CARLA velocity."""

import copy
import hashlib
import json
from pathlib import Path

from controller import FRAMES, MPH_TO_MPS, TARGET_MPH, command, validate_observed


def fixture(case):
    speed = TARGET_MPH[case] * MPH_TO_MPS
    return [{"video_frame": i, "time_s": i / 20, "observed_speed_mps": speed}
            for i in range(FRAMES)]


def reject(label, case, rows, expected):
    try:
        validate_observed(case, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    positive = [validate_observed(case, fixture(case)) for case in TARGET_MPH]
    assert command("slow", 0, 0)["throttle"] > 0
    assert command("fast", 0, 40 * MPH_TO_MPS)["brake"] > 0
    slow = fixture("slow")
    negative = [reject("wrong_speed", "fast", slow, "not observed"),
                reject("short_trace", "slow", slow[:-1], "incomplete 30-second")]
    bad = copy.deepcopy(slow)
    bad[250]["observed_speed_mps"] = float("nan")
    negative.append(reject("invalid_observed_speed", "slow", bad, "Missing original observed speed"))
    proof = {"format": "worker-cpu-default-speed-controller-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("controller-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
