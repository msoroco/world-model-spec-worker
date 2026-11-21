"""Source recording contract for the newly laid surface comparison."""

ASSIGNMENT = 'training__C183370__LVMC-11-22-100__motor_vehicle_driver'
CASES = ('newly_laid_crossing', 'newly_laid_avoidance')
CHANNELS = ('ego_pose', 'ego_body_footprint', 'warning_person_state',
            'pavement_footprint_contact')


def description(frames):
    if type(frames) is not int or frames < 600:
        raise ValueError('Newly laid recording needs at least 30 seconds')
    window = f'all {frames} frames / {frames/20:g} seconds'
    return {
        'channels': [{
            'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'derive from original CARLA actor/body/frame rows and surveyed laid-surface polygon',
            'time_window': window,
            'reference_frame': 'original CARLA frame joined to four source-camera videos',
            'uncertainty': '50 ms sampling; surface age, human warning and legal exception need independent original review',
        } for name in CHANNELS],
        'context_inputs': [{
            'name': 'surveyed_laid_region', 'unit': 'structured',
            'method': 'live map and actor readback joined to surveyed polygon; newly laid status unverified',
        }],
        'limitations': [
            'A nearby pedestrian does not establish a warning act.',
            'A surveyed polygon does not establish newly laid pavement.',
            'The paving-employee exception and legal outcome are unverified.',
        ],
    }


def config(case, frames):
    if case not in CASES:
        raise ValueError('Unknown newly laid case')
    return {'case_id': ASSIGNMENT + '__' + case, 'case_suffix': case,
            'law_id': 'LVMC-11-22-100', 'cell_id': 'C183370',
            'actor': 'motor_vehicle_driver', 'rate_hz': 20,
            'duration_s': frames / 20, 'recording_description': description(frames)}
