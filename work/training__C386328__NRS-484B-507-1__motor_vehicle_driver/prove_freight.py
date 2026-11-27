"""CPU source-shaped freight curb proof; observations are synthetic fixtures."""

import hashlib
import json
from pathlib import Path

from measure_freight import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "original_native_freight_zone_sources",
            "native_map_sha256": "1" * 64,
            "zone_marking_sha256": "2" * 64,
            "regulatory_sign_sha256": "3" * 64,
            "sign_hours_source_sha256": "4" * 64,
            "civil_time_source_sha256": "5" * 64,
            "vehicle_identity_sha256": "6" * 64,
            "material_activity_source_sha256": "7" * 64,
            "passenger_activity_source_sha256": "8" * 64,
            "waiting_vehicle_source_sha256": "9" * 64,
            "zone_kind": "freight_curb_loading",
            "effective_start_minute_local": 480,
            "effective_end_minute_local": 1020,
            "vehicle_id": "diagnostic_vehicle_1"}


def trace(*, material="none_observed", passenger="none_observed",
          waiting="none_observed", civil_minute=600):
    return [{"video_frame": i, "native_frame": 30000 + i,
             "time_s": i / 20, "source_cameras": {name: 30000 + i for name in CAMERAS},
             "civil_minute_local": civil_minute + i / 1200,
             "vehicle_id": "diagnostic_vehicle_1", "zone_occupancy": "within_marked_zone",
             "observed_speed_mps": 0.0,
             "material_activity": material,
             "passenger_activity": passenger,
             "material_vehicle_wait_state": waiting}
            for i in range(FRAMES)]


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    material = measure(context(), trace(material="pickup_loading"))
    idle = measure(context(), trace())
    passenger = measure(context(), trace(passenger="loading", waiting="waiting_to_enter"))
    inactive = measure(context(), trace(civil_minute=1100))
    assert material["material_handling_observed_frames"] == FRAMES
    assert idle["stopped_without_material_handling_frames"] == FRAMES
    assert passenger["passenger_exchange_with_waiting_material_vehicle_frames"] == FRAMES
    assert inactive["sign_effective_frames"] == 0
    negatives = []
    source = context()
    source.pop("regulatory_sign_sha256")
    negatives.append(reject("missing_sign_source", source, trace(), "source hash"))
    source = context()
    source["zone_kind"] = "passenger_loading"
    negatives.append(reject("wrong_zone_kind", source, trace(), "Freight curb"))
    source = context()
    source["effective_start_minute_local"] = 1200
    negatives.append(reject("invalid_hours", source, trace(), "sign hours"))
    negatives.append(reject("short_capture", context(), trace()[:-1], "Incomplete 30-second"))
    rows = trace()
    rows[300]["source_cameras"].pop("approach")
    negatives.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negatives.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[300]["vehicle_id"] = "other"
    negatives.append(reject("vehicle_identity_break", context(), rows, "Vehicle identity"))
    rows = trace()
    rows[300]["material_activity"] = None
    negatives.append(reject("unknown_material_source", context(), rows, "Material activity"))
    rows = trace()
    rows[300]["material_vehicle_wait_state"] = None
    negatives.append(reject("missing_wait_source", context(), rows, "wait source"))
    proof = {"format": "worker-cpu-freight-zone-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"material_loading": material, "idle_parking": idle,
                          "passenger_wait_context": passenger, "inactive_hours": inactive},
             "negative": negatives}
    path = Path(__file__).with_name("freight-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
