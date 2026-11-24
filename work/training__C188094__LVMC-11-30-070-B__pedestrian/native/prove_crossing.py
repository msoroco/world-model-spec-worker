"""CPU source-shaped diagnostics; no original Native pedestrian evidence."""

import copy
import hashlib
import json
from pathlib import Path

from measure_crossing import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "native_pedestrian_crossing_and_district_readback",
            "native_map_sha256": "1" * 64, "crosswalk_survey_sha256": "2" * 64,
            "business_district_evidence_sha256": "3" * 64,
            "overpass_geometry_sha256": "4" * 64,
            "pedestrian_identity_sha256": "5" * 64,
            "business_district_review": "source_supported_pending_independent_review",
            "roadway_bounds_m": {"min_x": -30, "max_x": 30, "min_y": -3, "max_y": 3},
            "crosswalks": [
                {"kind": "marked", "bounds_m": {"min_x": -2, "max_x": 2, "min_y": -3, "max_y": 3}},
                {"kind": "unmarked", "bounds_m": {"min_x": 20, "max_x": 22, "min_y": -3, "max_y": 3}}]}


def trace(x):
    rows = []
    for i in range(FRAMES):
        y = -6 if i < 100 else -6 + 12 * min(i - 100, 240) / 240
        rows.append({"video_frame": i, "native_frame": 12000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "pedestrian_x_m": x, "pedestrian_y_m": y,
                     "pedestrian_on_overpass_deck": False})
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
    marked, outside = trace(0), trace(12)
    a, b = measure(source, marked), measure(source, outside)
    assert a["roadway_entry_frame"] == b["roadway_entry_frame"]
    assert a["entry_crosswalk_kinds"] == ["marked"]
    assert b["entry_crosswalk_kinds"] == []
    assert a["entire_roadway_point_path_within_crosswalk"] is True
    assert b["entire_roadway_point_path_within_crosswalk"] is False
    unmarked = measure(source, trace(21))
    assert unmarked["entry_crosswalk_kinds"] == ["unmarked"]
    assert unmarked["entire_roadway_point_path_within_crosswalk"] is True
    drift_rows = trace(0)
    for i, row in enumerate(drift_rows):
        row["pedestrian_x_m"] = min(12.0, max(0.0, (i - 150) * .1))
    drift = measure(source, drift_rows)
    assert drift["entry_crosswalk_kinds"] == ["marked"]
    assert drift["entire_roadway_point_path_within_crosswalk"] is False
    assert drift["first_roadway_frame_outside_all_crosswalks"] > drift["roadway_entry_frame"]
    assert a["legal_compliance"] == b["legal_compliance"] == "unassessed"
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("business_district_evidence_sha256")
    negative.append(reject("missing_district_source", bad, marked, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["business_district_review"] = "unknown"
    negative.append(reject("unknown_district", bad, marked, "Business district source"))
    bad = copy.deepcopy(source)
    bad["crosswalks"] = []
    negative.append(reject("missing_crosswalk_survey", bad, marked, "Missing complete"))
    negative.append(reject("short_capture", source, marked[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(marked)
    bad_rows[220]["pedestrian_on_overpass_deck"] = True
    negative.append(reject("deck_not_roadway", source, bad_rows, "conflated with overpass deck"))
    bad_rows = copy.deepcopy(marked)
    bad_rows[220]["source_cameras"].pop("crosswalk_side")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    bad_rows = copy.deepcopy(marked)
    bad_rows[220]["pedestrian_x_m"] = 15
    negative.append(reject("pedestrian_teleport", source, bad_rows, "Pedestrian path continuity"))
    proof = {"format": "worker-cpu-business-district-crossing-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"marked": a, "outside": b},
             "path_diagnostics": {"unmarked": unmarked,
                                  "marked_entry_then_exit": drift},
             "negative": negative}
    path = Path(__file__).with_name("crossing-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
