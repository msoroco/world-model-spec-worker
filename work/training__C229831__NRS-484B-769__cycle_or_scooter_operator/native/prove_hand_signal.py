"""CPU-only positive and negative source-shape proof for hand-signal geometry."""
import json
from measure_hand_signal import FRAMES, FPS, measure


def context(machine_class="bicycle"):
    return {
        "machine_class": machine_class,
        "machine_class_source": "machine_actor_type_packet",
        "operator_id": "rider-1",
        "operator_id_source": "rider_mount_packet",
        "roadway_polygon_source": "map_roadway_polygon",
        "connected_right_turn_route_source": "route_waypoints",
        "keypoint_capture_source": "four_camera_keypoint_packet",
        "camera_calibration_source": "four_camera_calibration",
        "derived_channels_used": False,
    }


def rows(extended):
    output = []
    for i in range(FRAMES):
        right = extended and 100 <= i < 140
        output.append({
            "frame": i, "time_s": i / FPS, "operator_id": "rider-1",
            "roadway_occupied": True, "on_right_turn_route": 80 <= i < 250,
            "machine_centre_xy_m": [0, 0], "machine_heading_rad": 0,
            "right_shoulder_xy_m": [0, -0.18],
            "right_elbow_xy_m": [0, -0.50 if right else -0.30],
            "right_wrist_xy_m": [0, -0.80 if right else -0.42],
        })
    return output


def rejects(source, ctx, phrase):
    try:
        measure(source, ctx)
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
        return str(exc)
    raise AssertionError("invalid source was accepted")


if __name__ == "__main__":
    positive = measure(rows(True), context())
    comparison = measure(rows(False), context())
    assert positive["right_arm_extension_observed"]
    assert positive["right_arm_horizontal_rightward_runs"] == [
        {"first_frame": 100, "last_frame": 139, "duration_s": 2.0}
    ]
    assert not comparison["right_arm_extension_observed"]
    missing = rows(True)
    del missing[120]["right_wrist_xy_m"]
    badjoin = rows(True)
    badjoin[88]["time_s"] += 0.1
    wrong_actor = rows(True)
    wrong_actor[88]["operator_id"] = "rider-2"
    missing_context = context()
    del missing_context["roadway_polygon_source"]
    invalid_class = context("motorcycle")
    derived = context()
    derived["derived_channels_used"] = True
    negatives = {
        "missing_keypoint": rejects(missing, context(), "missing raw keypoint"),
        "bad_join": rejects(badjoin, context(), "frame identity"),
        "wrong_actor": rejects(wrong_actor, context(), "operator identity"),
        "missing_roadway_source": rejects(rows(True), missing_context, "sourced machine"),
        "wrong_machine": rejects(rows(True), invalid_class, "covered machine class"),
        "derived_only": rejects(rows(True), derived, "derived hand-signal"),
    }
    print(json.dumps({"positive": positive, "comparison": comparison, "negative_rejections": negatives}, sort_keys=True))
