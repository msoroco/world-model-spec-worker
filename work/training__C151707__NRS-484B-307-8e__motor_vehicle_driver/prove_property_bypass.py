"""CPU proof for source-separated red-signal property-route observations."""
import hashlib
import json
from pathlib import Path

from property_bypass_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def enc(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()


def sample(via_property=True, purpose="avoid_red_signal"):
    site = {
        "assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
        "approach_lane_id": "synthetic-lane-a", "intersecting_street_id": "synthetic-cross-b",
        "private_or_public_property_id": "synthetic-parcel-p", "property_boundary_source_id": "synthetic-parcel-survey",
        "approach_signal_id": "signal-a", "cross_street_signal_id": "signal-b",
    }
    intent = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample", "declared_purpose": purpose, "declaration_source_id": "synthetic-controller-plan"}
    frames = []
    for i in range(600):
        zone = "approach_road"
        if via_property and 200 <= i < 260:
            zone = "property"
        if via_property and i >= 260:
            zone = "intersecting_street"
        frames.append({"frame": i, "t_s": i / 20, "vehicle_id": "ego", "zone": zone,
                       "approach_signal": "steady_red_alone", "cross_street_signal": "not_red"})
    return {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample", "vehicle_id": "ego", "frames": frames}, site, intent


def reject(raw, site, intent, expected):
    try:
        measure(enc(raw), enc(site), enc(intent))
    except ValueError as exc:
        if str(exc) != expected:
            raise
        return
    raise RuntimeError("invalid source accepted: " + expected)


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    assert hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA
    assert hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA
    text = json.loads((source / "assignment.json").read_text())["law"]["text"]
    assert "private or public property" in text and "to avoid the red signal" in text
    raw, site, intent = sample()
    p = measure(enc(raw), enc(site), enc(intent))
    assert p["duration_s"] == 30 and p["first_property_frame"] == 200 and p["first_intersecting_street_frame"] == 260
    assert p["property_then_intersecting_street"] and p["steady_red_alone_at_property_entry"] and p["cross_street_not_red_at_entry"]
    assert p["declared_purpose"] == "avoid_red_signal" and p["legal_result"] is None
    raw, site, intent = sample(via_property=False)
    q = measure(enc(raw), enc(site), enc(intent))
    assert not q["property_then_intersecting_street"] and q["first_property_frame"] is None
    raw, site, intent = sample(purpose="other")
    other_purpose = measure(enc(raw), enc(site), enc(intent))
    assert other_purpose["property_then_intersecting_street"] and other_purpose["declared_purpose"] == "other"
    site["property_boundary_source_id"] = ""
    reject(raw, site, intent, "property boundary source missing")
    raw, site, intent = sample()
    intent["declaration_source_id"] = ""
    reject(raw, site, intent, "purpose source missing")
    raw, site, intent = sample()
    raw["frames"].pop(250)
    reject(raw, site, intent, "recording shorter than 30 seconds")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA, "via_property_frames_sha256": p["frame_source_sha256"], "road_only_frames_sha256": q["frame_source_sha256"], "purpose_sha256": p["purpose_declaration_sha256"], "checks": ["600_frame_20hz_30s", "route_through_property_vs_road_only", "purpose_separate_from_route", "property_source_rejection", "purpose_source_rejection", "short_capture_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
