"""Four distinct CPU construction policies per center-lane distance probe."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import TARGET_FEET,route


def parameters(case_suffix,candidate_id):
    if case_suffix not in TARGET_FEET:raise ValueError('Unknown C394300 case')
    if candidate_id not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    authored=route(case_suffix,start_x_m=-98 if candidate_id=='fallback1' else -95)
    knobs=EngineeringKnobs(lookahead_base_m=3 if candidate_id=='fallback2' else 4,
                           max_steer_fraction=1.0,target_speed_mps=9.0)
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'authored_route_xy_m':authored,
            'native_route_xy_m':[[x,-y] for x,y in authored],
            'route_start_x_m':-98 if candidate_id=='fallback1' else -95,
            'controller_knobs':knobs,'cameras':camera_plan(candidate_id),
            'comparison_commanded_distance_ft':TARGET_FEET[case_suffix],
            'requested_movement':'left_turn_from_center_lane',
            'law_id':'NRS-484B-223-3b','cell_id':'C394300',
            'actor':'motor_vehicle_driver','duration_s':24,'rate_hz':20}
