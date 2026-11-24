"""Source-separated roadside-stop diagnostic for NRS 484B.440(1).

It records statutory 200-foot sight distance numerically, but does not decide
whether stopping off the traveled way was practicable or an exception applies.
"""
import hashlib
import json

ASSIGNMENT = "training__C178965__NRS-484B-440-1__motor_vehicle_driver"
ASSIGNMENT_SHA = "2fd2554f74abfb3f4acd335fd278a92469b1daccab6318ed0a73a05061f09ae5"
WITNESS_SHA = "dff2e796f6e65d5ccafad632f4cd819b8bfd9c4614300a8d4c6656b45a2f1d43"
FEET_200_M = 60.96


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def measure(frame_bytes, road_bytes, context_bytes):
    packet, road, context = map(json.loads, (frame_bytes, road_bytes, context_bytes))
    require(all(x["assignment_id"] == ASSIGNMENT for x in (packet, road, context)), "assignment mismatch")
    kind = packet["source_kind"]
    require(kind in {"synthetic_native_sample", "native_saved_sample"} and road["source_kind"] == kind and context["source_kind"] == kind, "source kind mismatch")
    require(road["highway_source_id"] and road["district_source_id"] and road["district"] in {"business", "residence", "outside"}, "district/highway source missing")
    require(road["pavement_edge_source_id"] and road["pavement_left_y_m"] < road["pavement_right_y_m"], "pavement edge source missing")
    require(road["offroad_area_source_id"] and road["offroad_space_width_m"] >= 0, "offroad area source missing")
    require(context["disability_source_id"] and context["vehicle_disabled"] in {True, False, None}, "disability source missing")
    require(context["practicability_source_id"] and context["offroad_practicable"] in {True, False, None}, "practicability source missing")
    require(road["visibility_source_id"] and road["clear_view_forward_m"] >= 0 and road["clear_view_backward_m"] >= 0, "bidirectional sight source missing")
    frames = packet["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)), "noncontiguous 20 Hz frames")
    require(all(f["vehicle_id"] == packet["vehicle_id"] and f["speed_mps"] >= 0 and f["bbox_half_width_m"] > 0 for f in frames), "vehicle motion/footprint source missing")
    stationary = [f for f in frames if f["speed_mps"] <= 0.1]
    overlap = [f for f in stationary if f["y_m"] + f["bbox_half_width_m"] > road["pavement_left_y_m"]
               and f["y_m"] - f["bbox_half_width_m"] < road["pavement_right_y_m"]]
    width = road["pavement_right_y_m"] - road["pavement_left_y_m"]
    residual = []
    for f in overlap:
        occupied = min(road["pavement_right_y_m"], f["y_m"] + f["bbox_half_width_m"]) - max(road["pavement_left_y_m"], f["y_m"] - f["bbox_half_width_m"])
        residual.append({"frame": f["frame"], "unobstructed_pavement_width_m": round(width - occupied, 5)})
    return {
        "format": "c178965-saved-roadside-diagnostic-v1", "assignment_id": ASSIGNMENT,
        "source_kind": kind, "frame_sha256": digest(frame_bytes), "road_sha256": digest(road_bytes),
        "context_sha256": digest(context_bytes), "frame_count": len(frames), "duration_s": len(frames) / 20,
        "district": road["district"], "stationary_frames": [f["frame"] for f in stationary],
        "stationary_pavement_overlap_frames": [f["frame"] for f in overlap],
        "opposite_unobstructed_width_samples": residual,
        "clear_view_forward_m": road["clear_view_forward_m"],
        "clear_view_backward_m": road["clear_view_backward_m"],
        "measured_clear_view_at_least_200ft_each_direction": road["clear_view_forward_m"] >= FEET_200_M and road["clear_view_backward_m"] >= FEET_200_M,
        "offroad_space_width_m": road["offroad_space_width_m"],
        "offroad_practicable_context": context["offroad_practicable"],
        "vehicle_disabled_context": context["vehicle_disabled"],
        "legal_result": None,
        "unresolved": ["independent district/highway classification", "offroad practicability judgment", "disability exception and impossibility", "free-passage sufficiency", "physical source validity"],
    }
