"""Unselected LVMC exception scene variants and measured fallback decisions."""
from engineering_numeric import BASE, DELTA, TRIGGERS, evaluate as evaluate_trigger

CASES = {
    'exception_1_1': ('necessary_traffic_conflict', 'absent'),
    'exception_1_2': ('necessary_traffic_conflict', 'present'),
    'exception_2_1': ('compliance_with_law', 'absent'),
    'exception_2_2': ('compliance_with_law', 'present'),
    'exception_3_1': ('police_or_device_direction', 'absent'),
    'exception_3_2': ('police_or_device_direction', 'present'),
}
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SCENES = {
    'necessary_traffic_conflict': {
        'control': 'cross-road actor approaches the surveyed intersection while ego brakes and parks in the same C110454 parking bay',
        'native_source': 'original synchronized ego and other-actor poses plus intersection boundary readback',
        'measured_join': 'overlap between other-actor conflict occupancy frames and ego brake frames',
        'physical_review': 'other actor visibility, collision avoidance necessity, and original route response'},
    'compliance_with_law': {
        'control': 'ego response to an authored official stop-control device at the intersection',
        'native_source': 'NRS-484B-300-1 official-device obedience text hash, device state pixels and original ego action frames',
        'measured_join': 'cited law/source hash and ego action frames',
        'physical_review': 'device applicability to the exact parking behavior and original pixels'},
    'police_or_device_direction': {
        'control': 'authored traffic-control device direction visible near the intersection parking bay',
        'native_source': 'original pixels, device identifier, direction frame and joined ego action frames',
        'measured_join': 'direction pixel frame belongs to ego response frames',
        'physical_review': 'direction intelligibility, authority, applicability and original pixels'},
}


def plan(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exception case/candidate')
    branch, polarity = CASES[case]
    return {
        'case_suffix': case, 'candidate': candidate, 'exception_branch': branch,
        'requested_polarity': polarity, 'knobs': BASE | DELTA[candidate],
        'measured_trigger': TRIGGERS.get(candidate),
        'scene': SCENES[branch], 'physical_trigger_observed': False,
        'legal_exception_verdict': None,
    }


def parameters(case, candidate):
    return plan(case, candidate)


def controller_parameters(case, candidate):
    from controller import EngineeringKnobs
    knobs = plan(case, candidate)['knobs']
    return EngineeringKnobs(lookahead_base_m=knobs['route_lookahead_m'],
        target_speed_mps=5.5, final_brake_mps2=1.5,
        final_margin_m=knobs['parking_brake_start_m']-9.0)


def evaluate(candidate, source, expected_sha256):
    return evaluate_trigger(candidate, source, expected_sha256)
