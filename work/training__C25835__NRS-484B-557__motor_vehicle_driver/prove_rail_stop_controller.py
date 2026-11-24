"""Deterministic CPU controller tests, not Native motion evidence."""

import hashlib
import json
from pathlib import Path

from rail_stop_controller import RailStopController


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    positive = {}
    for case in ("probe_1", "probe_2"):
        controller = RailStopController(case, 0.0)
        target = controller.target_x
        assert controller.command(0, target - 20.0, 4.0, "occluded")["phase"] == "approach"
        assert controller.command(10, target - 2.0, 3.0, "occluded")["phase"] == "brake"
        assert controller.command(20, target, 0.0, "occluded")["phase"] == "hold"
        for frame in range(21, 41):
            assert controller.command(frame, target, 0.0, "occluded")["phase"] == "hold"
        assert controller.command(41, target, 0.0, "clear")["phase"] == "proceed"
        assert controller.command(42, target + 0.2, 0.4, "occluded")["phase"] == "hold"
        positive[case] = {"target_center_x_m": target, "visibility_loss_rebrakes": True}
    assert positive["probe_1"]["target_center_x_m"] < positive["probe_2"]["target_center_x_m"]
    negative = [
        reject("unknown_case", lambda: RailStopController("none", 0), "Unknown"),
        reject("missing_rail", lambda: RailStopController("probe_1", float("nan")), "rail geometry"),
        reject("missing_visibility", lambda: RailStopController("probe_1", 0).command(0, -20, 4, None), "visibility"),
        reject("overshot_stop", lambda: RailStopController("probe_1", 0).command(0, 0, 3, "clear"), "overshot"),
        reject("invalid_speed", lambda: RailStopController("probe_1", 0).command(0, -20, -1, "clear"), "pose or speed"),
    ]
    proof = {"format": "worker-cpu-rail-stop-controller-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative,
             "limitations": ["Controller commands are not measured motion", "Clear visibility is a conservative controller gate, not a due-care definition"]}
    path = Path(__file__).with_name("rail-stop-controller-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
