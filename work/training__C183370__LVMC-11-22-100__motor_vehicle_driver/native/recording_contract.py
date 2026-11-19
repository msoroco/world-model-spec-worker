"""Draft source recording contract for C183370 warning-person attempts."""

ASSIGNMENT = 'training__C183370__LVMC-11-22-100__motor_vehicle_driver'
CHANNELS = ('ego_pose', 'ego_body_footprint', 'warning_person_state',
            'pavement_footprint_contact')


def description(frames):
    if type(frames) is not int or frames < 600:
        raise ValueError('Recording contract needs at least 30 seconds')
    time_window = f'all {frames} frames / {frames/20:g} seconds'
    return {
        'channels': [{
            'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'derive from original CARLA actor/body/frame rows and surveyed pavement polygon',
            'time_window': time_window,
            'reference_frame': 'original CARLA frame joined to four source-camera videos',
            'uncertainty': '50 ms sampling; human warning, surface repair and legal exception require independent original review',
        } for name in CHANNELS],
        'context_inputs': [{
            'name': 'surveyed_repair_region', 'unit': 'structured',
            'method': 'live map and actor readback joined to the surveyed polygon; repair status unverified',
        }],
        'limitations': [
            'A nearby pedestrian does not establish an actual warning act.',
            'The surveyed polygon does not establish newly laid or repaired pavement.',
            'No paving-employee exception or legal conclusion is inferred.',
        ],
    }


def config(case, frames):
    if case not in ('reference', 'contrast'):
        raise ValueError('Unknown warning-person draft case')
    return {'case_id': ASSIGNMENT+'__'+case,
            'case_suffix': case, 'law_id': 'LVMC-11-22-100',
            'cell_id': 'C183370', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'duration_s': frames/20,
            'recording_description': description(frames)}
