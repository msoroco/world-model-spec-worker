"""Exact draft recording contract for C183370 non-person control routes."""
from recording_contract import ASSIGNMENT

CHANNELS = ('ego_pose', 'ego_body_footprint', 'control_actor_state',
            'pavement_footprint_contact')


def description(frames):
    if type(frames) is not int or frames < 600:
        raise ValueError('Variant recording needs at least 30 seconds')
    return {'channels': [{
        'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
        'method': 'derive from original CARLA actor/body/frame rows and surveyed pavement polygon',
        'time_window': f'all {frames} frames / {frames/20:g} seconds',
        'reference_frame': 'original CARLA frame joined to four source-camera videos',
        'uncertainty': '50 ms sampling; control content, surface repair and legal exception require independent original review',
    } for name in CHANNELS],
        'context_inputs': [{'name': 'surveyed_repair_region', 'unit': 'structured',
                            'method': 'live map and control-actor readback joined to surveyed polygon; repair status unverified'}],
        'limitations': ['Control actor proximity does not establish warning content.',
                        'Surveyed polygon does not establish newly laid or repaired pavement.',
                        'No paving-employee exception or legal conclusion is inferred.']}


def config(kind, route, frames):
    if kind not in ('barrier', 'warning_sign', 'highway_closed_sign') or route not in ('crossing', 'avoidance'):
        raise ValueError('Unknown exact non-person control case')
    return {'case_id': ASSIGNMENT + '__' + kind + '_' + route,
            'case_suffix': route, 'control_kind': kind,
            'law_id': 'LVMC-11-22-100', 'cell_id': 'C183370',
            'actor': 'motor_vehicle_driver', 'rate_hz': 20,
            'duration_s': frames / 20, 'frames': frames,
            'recording_description': description(frames)}
