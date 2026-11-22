"""Build the exact C125714 case config from a source-reviewed scene."""
from __future__ import annotations

from crossing_control import validate_routes
from runner import check_scene


ASSIGNMENT = "testing__C125714__NRS-484B-250-1__motor_vehicle_driver"


def recording_description():
    return {"channels": [
        {"name": "ego_body_history", "unit": "m"},
        {"name": "other_body_history", "unit": "m"}],
        "context_inputs": [
            {"name": name, "unit": "structured record"} for name in
            ("crossing_geometry", "highway_identity", "device_inventory", "driver_scope")],
        "capture_views": ["overview", "approach", "reference_corner", "driver_reference"],
        "physical_measurements": ["original body entry and clearance frames",
                                  "actual ego crossing departure"]}


def config(scene):
    check_scene(scene)
    validate_routes(scene)
    bounds = scene["crossing"]["bounds_xy_m"]
    route = scene["ego_route_xy_m"]
    delta = [route[-1][i] - route[0][i] for i in (0,1)]
    axis = 0 if abs(delta[0]) >= abs(delta[1]) else 1
    if delta[axis] == 0:
        raise ValueError("ego route has no departure direction")
    case_id = scene["case_id"]
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("case ID differs from exact assignment")
    description = recording_description()
    return {
        "law_id": "NRS-484B-250-1", "cell_id": "C125714",
        "actor": "motor_vehicle_driver", "selected_case_id": case_id,
        "rate_hz": 20, "duration_s": scene["duration_s"],
        "case": {"other_entered_first": scene["other_entered_first"],
                 "ego_response_request": scene.get("ego_response_request", "yield"),
                 "crossing_id": scene["crossing"]["crossing_id"],
                 "recording_description": description},
        "physical_completion": {
            "format": "worker-physical-completion-criteria",
            "criterion": "intersection_clearance",
            "motion_source": "ego-body-history.jsonl",
            "body_key": "body_vertices_xy_m",
            "intersection_polygon_xy_m": [[bounds[0],bounds[1]], [bounds[2],bounds[1]],
                                          [bounds[2],bounds[3]], [bounds[0],bounds[3]]],
            "exit_axis": axis, "exit_sign": 1 if delta[axis] > 0 else -1,
            "minimum_progress_m": .25, "minimum_samples": 2,
            "engineering_tolerances_not_legal": True,
            "context_sources": ["intersection-context.json"]},
    }
