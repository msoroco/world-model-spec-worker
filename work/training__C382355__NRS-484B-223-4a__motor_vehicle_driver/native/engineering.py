"""Four distinct construction policies for each 4(a) controlled probe."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import CASE_APPROACH_Y_M,route,straight_route


def parameters(case_suffix,candidate_id):
    if case_suffix not in CASE_APPROACH_Y_M:raise ValueError('Unknown 4(a) case')
    if candidate_id not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown candidate')
    station=-10 if candidate_id=='fallback1' else -7
    authored=route(-5.25,station) if case_suffix=='controlled_1' else straight_route(-5.25,station)
    knobs=EngineeringKnobs(lookahead_base_m=3 if candidate_id=='fallback2' else 4,
                           max_steer_fraction=1.0)
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'authored_route_xy_m':authored,'native_route_xy_m':authored,
            'turn_entry_x_m':station,'controller_knobs':knobs,
            'cameras':camera_plan(candidate_id),
            'comparison_approach_y_m':-5.25,
            'requested_movement':'right_turn' if case_suffix=='controlled_1' else 'straight_through',
            'law_id':'NRS-484B-223-4a','cell_id':'C382355',
            'actor':'motor_vehicle_driver','duration_s':24,'rate_hz':20}
