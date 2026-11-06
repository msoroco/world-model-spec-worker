"""Four distinct, unselected construction policies per 50-foot probe."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import TARGET_FEET,route


def parameters(case_suffix,candidate_id):
    if case_suffix not in TARGET_FEET: raise ValueError('Unknown 3(c) case')
    if candidate_id not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    start=42.0 if candidate_id=='fallback1' else 45.0
    authored=route(case_suffix,start_y_m=start)
    knobs=EngineeringKnobs(lookahead_base_m=3.0 if candidate_id=='fallback2' else 4.0,
                           max_steer_fraction=.7,target_speed_mps=5.0)
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'authored_route_xy_m':authored,
            'native_route_xy_m':[[x,-y] for x,y in authored],
            'inbound_start_y_authored_m':start,'controller_knobs':knobs,
            'cameras':camera_plan(candidate_id),
            'comparison_commanded_distance_ft':TARGET_FEET[case_suffix],
            'requested_movement':'left_turn_onto_highway_then_merge',
            'law_id':'NRS-484B-223-3c','cell_id':'C394300',
            'actor':'motor_vehicle_driver','duration_s':24,'rate_hz':20}
