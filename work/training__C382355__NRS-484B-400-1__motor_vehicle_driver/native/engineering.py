"""Four case-specific right-turn engineering proposals; no Native result."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import CASE_APPROACH_Y_M,route


def parameters(case_suffix,candidate_id):
    if case_suffix not in CASE_APPROACH_Y_M:raise ValueError('Unknown right-turn case')
    if candidate_id not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown construction candidate')
    turn_entry=-10 if candidate_id=='fallback1' else -7
    authored_route=route(CASE_APPROACH_Y_M[case_suffix],turn_entry)
    native_route=[[x,-y] for x,y in authored_route]
    knobs=EngineeringKnobs(lookahead_base_m=3.0 if candidate_id=='fallback2' else 4.0,
                           max_steer_fraction=1.0)
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'authored_route_xy_m':authored_route,'native_route_xy_m':native_route,
            'turn_entry_x_m':turn_entry,'controller_knobs':knobs,
            'cameras':camera_plan(candidate_id),
            'comparison_approach_y_m':CASE_APPROACH_Y_M[case_suffix],
            'law_id':'NRS-484B-400-1','cell_id':'C382355','actor':'motor_vehicle_driver',
            'duration_s':24,'rate_hz':20}
