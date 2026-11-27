"""CPU numeric rolling-hour and source-shaped 30-second capture proof."""

import copy
import hashlib
import json
from pathlib import Path

from measure_alley_parking import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "original_native_alley_parking_ledger",
            "native_map_sha256": "1" * 64,
            "alley_boundary_sha256": "2" * 64,
            "vehicle_identity_sha256": "3" * 64,
            "parking_ledger_sha256": "4" * 64,
            "civil_time_source_sha256": "5" * 64,
            "lawful_parking_review_sha256": "6" * 64,
            "alley_status": "source_surveyed_alley",
            "otherwise_lawful_review": "independently_reviewed",
            "vehicle_id": "diagnostic_vehicle_1"}


def ledger(intervals, *, end=3600):
    return {"span_start_s": 0, "span_end_s": end, "capture_start_s": 0,
            "parked_intervals": [
                {"vehicle_id": "diagnostic_vehicle_1", "start_s": start,
                 "end_s": finish, "within_alley": True,
                 "otherwise_lawful_reviewed": True}
                for start, finish in intervals]}


def capture():
    return [{"video_frame": i, "native_frame": 23000 + i,
             "time_s": i / 20, "source_cameras": {name: i for name in CAMERAS},
             "vehicle_id": "diagnostic_vehicle_1", "within_alley": True}
            for i in range(FRAMES)]


def reject(label, source, parking, rows, expected):
    try:
        measure(source, parking, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    short = measure(context(), ledger([(0, 1500)]), capture())
    long = measure(context(), ledger([(0, 2100)]), capture())
    exact = measure(context(), ledger([(0, 1800)]), capture())
    split = measure(context(), ledger([(0, 1200), (1800, 2700)]), capture())
    assert short["max_parked_seconds_in_sourced_rolling_hour"] == 1500
    assert long["max_parked_seconds_in_sourced_rolling_hour"] == 2100
    assert exact["measured_greater_than_30_minutes"] is False
    assert split["max_parked_seconds_in_sourced_rolling_hour"] == 2100
    negatives = []
    source = context()
    source.pop("parking_ledger_sha256")
    negatives.append(reject("missing_ledger_hash", source, ledger([(0, 1500)]), capture(), "source hash"))
    source = context()
    source["otherwise_lawful_review"] = "unknown"
    negatives.append(reject("unreviewed_prerequisite", source, ledger([(0, 1500)]), capture(), "prerequisite"))
    negatives.append(reject("short_ledger", context(), ledger([(0, 1500)], end=3500), capture(), "less than one hour"))
    negatives.append(reject("overlapping_intervals", context(), ledger([(0, 1200), (1000, 1800)]), capture(), "double count"))
    parking = ledger([(0, 1500)])
    parking["parked_intervals"][0]["within_alley"] = False
    negatives.append(reject("outside_alley_interval", context(), parking, capture(), "alley/lawful"))
    negatives.append(reject("short_capture", context(), ledger([(0, 1500)]), capture()[:-1], "Incomplete 30-second"))
    rows = capture()
    rows[300]["source_cameras"].pop("driver_reference")
    negatives.append(reject("missing_camera", context(), ledger([(0, 1500)]), rows, "Four source camera"))
    rows = capture()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negatives.append(reject("duplicate_native_frame", context(), ledger([(0, 1500)]), rows, "Native frame"))
    rows = capture()
    rows[300]["vehicle_id"] = "other_vehicle"
    negatives.append(reject("vehicle_identity_break", context(), ledger([(0, 1500)]), rows, "vehicle identity"))
    proof = {"format": "worker-cpu-alley-parking-hour-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"25_minutes": short, "35_minutes": long,
                          "exact_30_minutes": exact, "split_20_plus_15_minutes": split},
             "negative": negatives}
    path = Path(__file__).with_name("alley-parking-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
