"""CPU proof of saved parking geometry and source rejection."""
import hashlib
import json
from pathlib import Path

from parking_saved_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def enc(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()


def sample(x=15.0, official=True):
    inventory = {
        "assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
        "road_type": "highway", "narrow_section_source_id": "synthetic-map-width-survey",
        "measured_road_width_m": 4.0, "device_id": "device-1", "device_erected": True,
        "device_official_source_id": "synthetic-authority-record" if official else "",
        "device_prohibits_parking": True, "governed_extent_xyxy_m": [0.0, -2.0, 30.0, 2.0],
    }
    frames = [{
        "frame": i, "t_s": i / 20, "vehicle_id": "ego",
        "x_m": x, "y_m": 0.0, "bbox_half_length_m": 2.0,
        "bbox_half_width_m": 0.8, "speed_mps": 0.0 if 200 <= i < 400 else 4.0,
    } for i in range(600)]
    return {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample", "vehicle_id": "ego", "frames": frames}, inventory


def reject(packet, inventory, expected):
    try:
        measure(enc(packet), enc(inventory))
    except ValueError as exc:
        if str(exc) != expected:
            raise
        return
    raise RuntimeError("invalid source accepted: " + expected)


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "inputs" / ASSIGNMENT
    assert hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA
    assert hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    assert "official traffic-control devices" in law and "narrow highway" in law
    inside, inventory = sample()
    p = measure(enc(inside), enc(inventory))
    assert p["duration_s"] == 30 and p["stationary_frame_count"] == 200
    assert p["stationary_footprint_fully_within_governed_extent_frames"] == list(range(200, 400))
    assert p["legal_result"] is None
    outside, fixed = sample(x=35.0)
    q = measure(enc(outside), enc(fixed))
    assert q["stationary_frame_count"] == 200
    assert q["stationary_footprint_fully_within_governed_extent_frames"] == []
    unverified, bad = sample(official=False)
    reject(unverified, bad, "official-device authority missing")
    broken, fixed = sample()
    broken["frames"][300]["vehicle_id"] = "intruder"
    reject(broken, fixed, "vehicle identity changed")
    broken, fixed = sample()
    broken["frames"].pop(300)
    reject(broken, fixed, "recording shorter than 30 seconds")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA, "inside_packet_sha256": p["packet_sha256"], "outside_packet_sha256": q["packet_sha256"], "inventory_sha256": p["inventory_sha256"], "checks": ["600_frame_20hz_30s", "parked_footprint_inside_vs_outside", "official_device_source_rejection", "participant_identity_rejection", "missing_frame_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
