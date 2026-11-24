"""Four straight-through engineering policies per C382389 controlled probe."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import CASE_APPROACH_Y_M,route


def parameters(case_suffix,candidate_id):
    if case_suffix not in CASE_APPROACH_Y_M:raise ValueError('Unknown C382389 case')
    if candidate_id not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    station=-10 if candidate_id=='fallback1' else -7
    lateral=CASE_APPROACH_Y_M[case_suffix]
    authored=route(lateral,station)
    knobs=EngineeringKnobs(lookahead_base_m=3 if candidate_id=='fallback2' else 4,
                           max_steer_fraction=1.0)
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'authored_route_xy_m':authored,'native_route_xy_m':[[x,-y] for x,y in authored],
            'route_start_variant_m':station,'controller_knobs':knobs,
            'cameras':camera_plan(candidate_id),
            'comparison_approach_y_m':lateral,
            'requested_movement':'straight_through',
            'law_id':'NRS-484B-223-4b','cell_id':'C382389',
            'actor':'motor_vehicle_driver','duration_s':24,'rate_hz':20}
