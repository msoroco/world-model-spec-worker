"""CPU authored-scene proof; no CARLA world or hour-long recording."""

import copy
import hashlib
import json
from pathlib import Path

from alley_scene import hold_command, scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    short, long = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(short), validate_request(long)]
    assert short["road_opendrive"] == long["road_opendrive"]
    for key in ("vehicle", "alley", "cameras"):
        assert short[key] == long[key]
    assert short["requested_total_parked_seconds_in_hour"] == 1500
    assert long["requested_total_parked_seconds_in_hour"] == 2100
    assert hold_command("probe_1", 0, 0.0)["observed_stopped"] is True
    assert hold_command("probe_2", 599, 2.0)["observed_stopped"] is False
    missing_camera = copy.deepcopy(short)
    missing_camera["cameras"].pop()
    false_hour = copy.deepcopy(short)
    false_hour["separate_original_hour_ledger_required"] = False
    negative = [
        reject("unknown_case", lambda: scene_request("none"), "Unknown"),
        reject("bad_alley_prop", lambda: scene_request("probe_1", wall_blueprint="vehicle.car"), "alley prop"),
        reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
        reject("false_hour_proof", lambda: validate_request(false_hour), "cannot assert"),
        reject("missing_native_speed", lambda: hold_command("probe_1", 0, None), "Native speed"),
    ]
    proof = {"format": "worker-cpu-alley-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_condition_checks": ["road", "vehicle pose", "alley props", "cameras"],
             "difference": "requested total parked seconds from separate hour ledger"}
    path = Path(__file__).with_name("alley-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
