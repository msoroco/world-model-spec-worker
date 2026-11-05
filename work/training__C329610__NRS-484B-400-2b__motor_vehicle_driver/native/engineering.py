"""Exit-side candidate settings for two controlled cases, CPU proposal only."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import EXIT_X_M, route


def parameters(case_suffix, candidate_id):
    if case_suffix not in EXIT_X_M:
        raise ValueError("Unknown exit-side case")
    if candidate_id not in ("primary", "fallback1", "fallback2", "fallback3"):
        raise ValueError("Unknown candidate")
    turn_entry_x = -10 if candidate_id == "fallback1" else -7
    authored_route = route(EXIT_X_M[case_suffix], turn_entry_x_m=turn_entry_x)
    native_route = [[x, -y] for x, y in authored_route]
    knobs = EngineeringKnobs(lookahead_base_m=3.0 if candidate_id == "fallback2" else 4.0)
    return {"authored_route_xy_m":authored_route,
            "native_route_xy_m":native_route,
            "turn_entry_x_m":turn_entry_x,
            "controller_knobs":knobs,
            "cameras":camera_plan(candidate_id),
            "comparison_exit_x_m":EXIT_X_M[case_suffix],
            "law_id":"NRS-484B-400-2b", "cell_id":"C329610",
            "actor":"motor_vehicle_driver", "duration_s":24, "rate_hz":20}
