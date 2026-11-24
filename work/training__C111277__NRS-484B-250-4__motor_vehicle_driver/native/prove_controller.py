"""Exercise the 20 Hz controller with source-shaped 30-second input traces."""
import argparse
import hashlib
import json
from pathlib import Path

from controller import InoperativeSignalController, Observation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_trace(activation=True, crosswalk=True, stop_line=False, conflict=True):
    controller = InoperativeSignalController()
    phases = []
    for frame in range(600):
        distance = max(0.1, 35 - frame * 0.1)
        speed = 0.0 if 150 <= frame < 251 else 2.0
        obs = Observation(
            frame, True, True, activation, True, stop_line, crosswalk,
            distance, speed, conflict and frame <= 240,
            conflict and 120 <= frame <= 240,
        )
        phases.append(controller.step(obs).phase)
    return phases


def reject(**kwargs):
    try:
        run_trace(**kwargs)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("invalid activation was accepted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    phases = run_trace()
    assert len(phases) == 600
    assert phases[150] == "hold" and phases[169] == "yield"
    assert all(p != "released" for p in phases[:241])
    assert phases[241] == "released"
    assert all(p == "released" for p in phases[241:])
    no_conflict = run_trace(conflict=False)
    assert no_conflict[169] == "released"
    negatives = {
        "operating_signal": reject(activation=False),
        "missing_crosswalk": reject(crosswalk=False),
        "unexpected_stop_line": reject(stop_line=True),
    }
    assert "activation" in negatives["operating_signal"]
    assert "crosswalk" in negatives["missing_crosswalk"]
    assert "stop-line" in negatives["unexpected_stop_line"]
    result = {
        "format": "nrs-484b-250-4-controller-proof-v1",
        "passed": True,
        "controller_sha256": sha(Path(__file__).with_name("controller.py")),
        "frames": 600, "rate_hz": 20,
        "first_hold_frame": 150, "yield_enter_frame": 169,
        "release_after_conflict_frame": 241,
        "release_without_conflict_frame": 169,
        "negative_rejections": negatives,
        "source_kind": "synthetic_native_sample",
        "physical_result_claimed": False,
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "frames": 600,
                      "release_after_conflict_frame": 241,
                      "negative_cases": len(negatives)}))


if __name__ == "__main__":
    main()
