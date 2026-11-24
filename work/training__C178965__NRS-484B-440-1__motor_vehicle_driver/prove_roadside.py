"""CPU pair for pavement occupancy, width and 200-foot sight measurements."""
import hashlib
import json
from pathlib import Path
from roadside_saved_measure import ASSIGNMENT, ASSIGNMENT_SHA, WITNESS_SHA, measure


def enc(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":")).encode()


def sample(y=2.8, disabled=False, backward_sight=80.0):
    road = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
            "highway_source_id": "synthetic-road-survey", "district_source_id": "synthetic-district-survey", "district": "outside",
            "pavement_edge_source_id": "synthetic-edge-survey", "pavement_left_y_m": -3.5, "pavement_right_y_m": 3.5,
            "offroad_area_source_id": "synthetic-shoulder-survey", "offroad_space_width_m": 3.0,
            "visibility_source_id": "synthetic-sight-survey", "clear_view_forward_m": 80.0, "clear_view_backward_m": backward_sight}
    context = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
               "disability_source_id": "synthetic-vehicle-condition", "vehicle_disabled": disabled,
               "practicability_source_id": "synthetic-route-assessment", "offroad_practicable": True}
    frames = [{"frame": i, "t_s": i / 20, "vehicle_id": "ego", "y_m": y,
               "speed_mps": 0.0 if 200 <= i < 400 else 4.0, "bbox_half_width_m": 0.9}
              for i in range(600)]
    return {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample", "vehicle_id": "ego", "frames": frames}, road, context


def reject(packet, road, context, expected):
    try:
        measure(enc(packet), enc(road), enc(context))
    except ValueError as exc:
        if str(exc) != expected:
            raise
        return
    raise RuntimeError("invalid source accepted")


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    assert hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA
    assert hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA
    text = json.loads((source / "assignment.json").read_text())["law"]["text"]
    assert "200 feet in each direction" in text and "disabled" in text
    packet, road, context = sample()
    inside = measure(enc(packet), enc(road), enc(context))
    assert inside["duration_s"] == 30 and inside["stationary_pavement_overlap_frames"] == list(range(200, 400))
    assert inside["opposite_unobstructed_width_samples"][0]["unobstructed_pavement_width_m"] == 5.4
    assert inside["measured_clear_view_at_least_200ft_each_direction"] and inside["legal_result"] is None
    packet, road, context = sample(y=5.0)
    outside = measure(enc(packet), enc(road), enc(context))
    assert outside["stationary_frames"] == list(range(200, 400)) and outside["stationary_pavement_overlap_frames"] == []
    packet, road, context = sample(disabled=True, backward_sight=50.0)
    exception = measure(enc(packet), enc(road), enc(context))
    assert exception["vehicle_disabled_context"] is True and not exception["measured_clear_view_at_least_200ft_each_direction"]
    road["visibility_source_id"] = ""
    reject(packet, road, context, "bidirectional sight source missing")
    packet, road, context = sample()
    packet["frames"].pop(250)
    reject(packet, road, context, "recording shorter than 30 seconds")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA, "witness_sha256": WITNESS_SHA,
                      "on_pavement_frame_sha256": inside["frame_sha256"], "off_pavement_frame_sha256": outside["frame_sha256"],
                      "checks": ["600_frame_30s_20hz", "on_vs_off_pavement_footprint", "residual_width_measurement", "statutory_200ft_sight", "disability_context_separate", "missing_sight_source_rejection", "short_capture_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
