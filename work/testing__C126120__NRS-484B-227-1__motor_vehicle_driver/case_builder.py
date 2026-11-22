"""Source-bound exact case configuration for the median-opening U-turn."""
from __future__ import annotations

from uturn_control import validate_scene
from divider_construction import validate_divider

ASSIGNMENT = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver"
CASE_SUFFIXES = ("opening_single", "opening_multiple", "closed_divider",
                 "wrong_roadway", "crossover_candidate", "intersection_candidate",
                 "right_roadway_no_turn")


def recording_description():
    channels = []
    for name, unit, method in (
        ("ego_body_history", "m", "Original CARLA eight-vertex box projected to four XY corners"),
        ("ego_heading_history", "deg", "Original CARLA actor transform yaw"),
        ("ego_velocity_history", "m/s", "Original CARLA actor velocity XY components")):
        channels.append({"name":name,"unit":unit,"method":method,
            "time_window":"every captured original frame", "reference_frame":"live OpenDRIVE XY world",
            "uncertainty":"CARLA source sampling and body geometry; no legal threshold",
            "sampling_rate_hz":20})
    return {"channels":channels,
        "context_inputs":[
            {"name":"median_geometry","unit":"structured record",
             "method":"retained reviewed median packet and exact live OpenDRIVE SHA"},
            {"name":"authority_review","unit":"structured record",
             "method":"separately retained administrative review source; judgment unresolved"}],
        "limitations":["Physical opening and roadway measurements do not decide statutory exceptions.",
                       "Public-authority establishment requires independent source review."]}


def config(scene):
    validate_scene(scene)
    validate_divider(scene)
    case_id = scene["case_id"]
    if case_id not in {ASSIGNMENT+"__"+suffix for suffix in CASE_SUFFIXES}:
        raise ValueError("case ID differs from exact assignment")
    return {"law_id":"NRS-484B-227-1", "cell_id":"C126120",
        "actor":"motor_vehicle_driver", "selected_case_id":case_id,
        "supported_case_ids":[ASSIGNMENT+"__"+suffix for suffix in CASE_SUFFIXES],
        "rate_hz":20, "duration_s":scene["duration_s"],
        "vehicle_blueprint_id":scene.get("vehicle_blueprint_id"),
        "cameras":[
            {"name":name,"width":width,"height":height,"fov_deg":90,
             "pose_strategy":strategy}
            for name,width,height,strategy in (
                ("overview",1920,1080,"top_down_centered_on_reviewed_median_opening"),
                ("approach",1280,720,"source_right_roadway_toward_opening"),
                ("reference_corner",1280,720,"closed_divider_and_opening_corner"),
                ("driver_reference",1280,720,"ego_attached_driver_reference"))],
        "case":{"opening_id":scene["context"]["opening_id"],
                "multiple_movement_requested":"reverse" in scene["segment_directions"],
                "recording_description":recording_description()},
        "physical_completion":{"format":"worker-physical-completion-criteria",
            "criterion":"turn", "motion_source":"ego-body-history.jsonl",
            "body_key":"body_vertices_xy_m", "heading_key":"heading_deg",
            "context_sources":["median-context.json"],
            "turn_degrees":180, "turn_tolerance_deg":30,
            "minimum_progress_m":.25, "minimum_samples":3,
            "engineering_tolerances_not_legal":True}}
