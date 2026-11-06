"""Exact four candidate engineering settings for both controlled cases."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import CASE_PLACEMENTS, route


def parameters(case_suffix, candidate_id):
    if case_suffix not in CASE_PLACEMENTS:
        raise ValueError("Unknown controlled case")
    if candidate_id not in ("primary", "fallback1", "fallback2", "fallback3"):
        raise ValueError("Unknown candidate")
    turn_entry_x = -10 if candidate_id == "fallback1" else -7
    authored_route = route(CASE_PLACEMENTS[case_suffix], turn_entry_x_m=turn_entry_x)
    # CARLA's OpenDRIVE lane transform reflects Y into its Native world frame.
    # See https://carla.org/Doxygen/html/dc/d13/Lane_8cpp_source.html
    native_route = [[x, -y] for x, y in authored_route]
    knobs = EngineeringKnobs(lookahead_base_m=3.0 if candidate_id == "fallback2" else 4.0)
    return {"authored_route_xy_m":authored_route,
            "native_route_xy_m":native_route,
            "turn_entry_x_m":turn_entry_x,
            "controller_knobs":knobs,
            "cameras":camera_plan(candidate_id),
            "comparison_lateral_m":CASE_PLACEMENTS[case_suffix],
            "law_id":"NRS-484B-400-2a","cell_id":"C329610",
            "actor":"motor_vehicle_driver","duration_s":24,"rate_hz":20}
