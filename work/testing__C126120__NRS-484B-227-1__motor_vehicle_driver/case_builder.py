"""Source-bound exact case configuration for the median-opening U-turn."""
from __future__ import annotations

from uturn_control import validate_scene

ASSIGNMENT = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver"


def recording_description():
    return {"channels": [
        {"name":"ego_body_history", "unit":"m"},
        {"name":"ego_heading_history", "unit":"deg"},
        {"name":"ego_velocity_history", "unit":"m/s"}],
        "context_inputs": [
            {"name":"median_geometry", "unit":"structured record"},
            {"name":"authority_review", "unit":"structured record"}],
        "capture_views": ["overview", "approach", "reference_corner", "driver_reference"],
        "physical_measurements": ["original full-body opening and divider contact",
                                  "source/destination right-roadway occupancy",
                                  "net heading reversal and realized reverse motion"]}


def config(scene):
    validate_scene(scene)
    case_id = scene["case_id"]
    if not case_id.startswith(ASSIGNMENT+"__"):
        raise ValueError("case ID differs from exact assignment")
    return {"law_id":"NRS-484B-227-1", "cell_id":"C126120",
        "actor":"motor_vehicle_driver", "selected_case_id":case_id,
        "rate_hz":20, "duration_s":scene["duration_s"],
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
