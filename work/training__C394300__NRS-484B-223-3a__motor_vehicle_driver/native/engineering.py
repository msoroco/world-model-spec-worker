"""Four distinct unselected CPU construction policies for each 3(a) case."""
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import CASES,route

CANDIDATES=('primary','fallback1','fallback2','fallback3')


def parameters(case,candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or construction candidate')
    start=-98 if candidate=='fallback1' else -95
    advance=5 if candidate=='fallback1' else 0
    authored=route(case,start_x=start,entry_advance_m=advance)
    knobs=EngineeringKnobs(lookahead_base_m=2.5 if candidate=='fallback2' else 4,
                           max_steer_fraction=1.0 if candidate=='fallback2' else .75,
                           target_speed_mps=9.0 if candidate=='fallback2' else 10.0)
    knobs.validate()
    return {'case':case,'candidate':candidate,'law_id':'NRS-484B-223-3a',
            'authored_route_xy_m':authored,'native_route_xy_m':[[x,-y] for x,y in authored],
            'controller_knobs':knobs,'camera_plan':camera_plan(candidate),
            'entry_advance_m':advance,'route_start_x_m':start,
            'purpose_request':('left_turn_from_center_at_first_opportunity' if case=='controlled_1'
                               else 'through_travel_then_later_left_from_through_lane'),
            'purpose_request_is_observation':False,'physical_success_claimed':False}
