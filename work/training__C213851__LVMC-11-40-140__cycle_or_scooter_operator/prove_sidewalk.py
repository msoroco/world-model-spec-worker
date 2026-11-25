"""CPU proof of crossing order, pre-entry cessation and pedestrian timing."""
import hashlib
import json
from pathlib import Path
from sidewalk_saved_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def enc(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()


def sample(stop=True, pedestrian_clear=True):
    site = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT+'__probe_01',
            "pedestrian_conflict_source_id": "synthetic-pedestrian-conflict-survey",
            "source_kind": "synthetic_native_sample",
            "district": "residence", "district_source_id": "synthetic-district-survey",
            "origin_kind": "driveway", "origin_source_id": "synthetic-driveway-survey",
            "travel_direction": "into_driveway",
            "sidewalk_continuation_across_origin": True,
            "sidewalk_continuation_source_id": "synthetic-sidewalk-survey",
            "sidewalk_boundary_source_id": "synthetic-boundary-survey",
            "rider_class": "bicycle", "rider_class_source_id": "synthetic-blueprint-record"}
    frames = []
    for i in range(600):
        frames.append({"frame": i, "t_s": i / 20, "rider_id": "rider", "pedestrian_id": "ped",
                       "rider_s_m": -1.0 if i < 200 else 0.01 + 0.05 * (i - 200),
                       "rider_speed_mps": 0.0 if stop and 180 <= i < 200 else 2.0,
                       "pedestrian_on_crossing": 175 <= i < (195 if pedestrian_clear else 215)})
    return {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
            "rider_id": "rider", "pedestrian_id": "ped", "frames": frames}, site


def reject(packet, site, expected):
    try:
        measure(enc(packet), enc(site))
    except ValueError as exc:
        if str(exc) != expected:
            raise
        return
    raise RuntimeError("invalid source accepted")


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    assert hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA
    assert hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    assert "immediately prior" in law and "pedestrian" in law
    packet, site = sample()
    p = measure(enc(packet), enc(site))
    assert p["duration_s"] == 30 and p["sidewalk_entry_frame"] == 200
    assert p["pre_entry_near_zero_frames"] == list(range(180, 200)) and not p["pedestrian_on_crossing_at_entry"]
    packet, site = sample(stop=False, pedestrian_clear=False)
    q = measure(enc(packet), enc(site))
    assert q["pre_entry_near_zero_frames"] == [] and q["pedestrian_on_crossing_at_entry"]
    site["sidewalk_continuation_source_id"] = ""
    reject(packet, site, "sidewalk continuation source missing")
    packet, site = sample()
    packet["frames"].pop(250)
    reject(packet, site, "recording shorter than 30 seconds")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA,
                      "stop_and_yield_source_sha256": p["frame_sha256"], "no_stop_conflict_source_sha256": q["frame_sha256"],
                      "checks": ["600_frame_30s_20hz", "stop_before_sidewalk", "pedestrian_clearance_timing", "no_stop_conflict_contrast", "sidewalk_source_rejection", "short_capture_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
