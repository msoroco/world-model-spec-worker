"""CPU authored freight-zone scene proof; no original CARLA observation."""

import copy
import hashlib
import json
from pathlib import Path

from freight_scene import scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    scenes = {key: scene_request(key) for key in ("probe_1", "probe_2", "probe_3", "probe_4", "probe_5")}
    loading, idle = scenes["probe_1"], scenes["probe_2"]
    positive = [validate_request(scene) for scene in scenes.values()]
    assert loading["road_opendrive"] == idle["road_opendrive"]
    for key in ("vehicle", "zone", "sign", "cameras"):
        assert loading[key] == idle[key]
    assert loading["material"]["requested_activity"] == "pickup_loading"
    assert idle["material"]["requested_activity"] == "none_requested"
    assert scenes["probe_2"]["civil_time"]["requested_minute_local"] == 720
    assert scenes["probe_3"]["civil_time"]["requested_minute_local"] == 1100
    assert scenes["probe_4"]["passenger"]["requested_activity"] == "loading"
    assert scenes["probe_5"]["passenger"]["requested_activity"] == "loading"
    assert not scenes["probe_4"]["material_transport_vehicle"]["requested_waiting_to_enter"]
    assert scenes["probe_5"]["material_transport_vehicle"]["requested_waiting_to_enter"]
    missing_camera = copy.deepcopy(loading)
    missing_camera["cameras"].pop()
    false_sign = copy.deepcopy(loading)
    false_sign["sign"]["actual_text_and_hours_verified"] = True
    false_class_review = copy.deepcopy(scenes["probe_5"])
    false_class_review["material_transport_vehicle"]["source_class_and_interference_review_required"] = False
    negative = [
        reject("unknown_case", lambda: scene_request("none"), "Unknown"),
        reject("bad_sign_prop", lambda: scene_request("probe_1", sign_blueprint="vehicle.car"), "sign or material"),
        reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
        reject("false_sign_claim", lambda: validate_request(false_sign), "cannot assert"),
        reject("false_class_claim", lambda: validate_request(false_class_review), "class and interference review"),
    ]
    proof = {"format": "worker-cpu-freight-zone-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_condition_checks": ["one-way road", "vehicle pose", "zone", "sign", "cameras"],
             "controlled_differences": ["material activity at fixed effective hours",
                                        "effective versus inactive signed hours at fixed inactivity",
                                        "actual passenger-loading request versus no exchange",
                                        "materials-vehicle waiting request during passenger exchange"]}
    path = Path(__file__).with_name("freight-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
