"""CPU source-shaped diagnostics, not original Native vehicle observations."""

import copy
import hashlib
import json
from pathlib import Path

from measure_trail import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "native_trail_map_and_document_readback",
            "native_map_sha256": "1" * 64,
            "designation_document_sha256": "2" * 64,
            "dedication_document_sha256": "3" * 64,
            "posted_sign_pixel_sha256": "4" * 64,
            "vehicle_identity_sha256": "5" * 64,
            "official_designation": "nonmotorized_trail", "city_dedication": True,
            "posted_prohibition": True, "vehicle_class": "motorized_vehicle",
            "barrier_clear_gap_m": 3.2, "vehicle_width_m": 1.9,
            "trail_right_of_way_m": {"min_x": 10, "max_x": 90, "min_y": -2, "max_y": 2}}


def trace(inside):
    rows = []
    for i in range(FRAMES):
        center_y = 0 if inside else 6
        rows.append({"video_frame": i, "native_frame": 9000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "vehicle_footprint_m": {"min_x": -50 + i * 0.2 - 2,
                                             "max_x": -50 + i * 0.2 + 2,
                                             "min_y": center_y - 0.9,
                                             "max_y": center_y + 0.9}})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    source = context()
    outside = trace(False)
    within = trace(True)
    a = measure(source, outside)
    b = measure(source, within)
    assert a["frame_count"] == b["frame_count"] == 600
    assert a["occupancy_frames"] == 0 and b["occupancy_frames"] > 0
    assert not a["ever_within_right_of_way"] and b["ever_within_right_of_way"]
    assert a["legal_compliance"] == b["legal_compliance"] == "unassessed"
    negative = []
    for field, expected in (("designation_document_sha256", "Missing source hash"),
                            ("dedication_document_sha256", "Missing source hash"),
                            ("posted_sign_pixel_sha256", "Missing source hash")):
        bad = copy.deepcopy(source)
        bad.pop(field)
        negative.append(reject("missing_" + field, bad, within, expected))
    bad = copy.deepcopy(source)
    bad["official_designation"] = "unknown"
    negative.append(reject("unknown_designation", bad, within, "Official trail designation"))
    bad = copy.deepcopy(source)
    bad["city_dedication"] = False
    negative.append(reject("missing_dedication", bad, within, "City dedication"))
    bad = copy.deepcopy(source)
    bad["barrier_clear_gap_m"] = 1.0
    negative.append(reject("blocked_barrier", bad, within, "vehicle clearance"))
    negative.append(reject("short_capture", source, within[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(within)
    bad_rows[200]["source_cameras"].pop("trail_side")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    bad_rows = copy.deepcopy(within)
    bad_rows[200]["native_frame"] = bad_rows[199]["native_frame"]
    negative.append(reject("repeated_native_frame", source, bad_rows, "Native frame identity"))
    proof = {"format": "worker-cpu-trail-occupancy-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"outside": a, "within": b}, "negative": negative}
    path = Path(__file__).with_name("trail-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
