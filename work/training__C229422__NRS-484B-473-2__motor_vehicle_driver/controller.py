"""Selected NRS 484B.473(2) Native lamp requests, never optical findings."""

CASE_MODES = {
    'witness_1': 'depressed_low_beam',
    'witness_2': 'undepressed_high_beam',
    'exception_1_1': 'undepressed_high_beam',
    'exception_1_2': 'undepressed_high_beam_with_parking',
}
FRAMES = 600
RATE_HZ = 20


def light_request(case_suffix, frame):
    if case_suffix not in CASE_MODES or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Unknown selected case or frame')
    mode = CASE_MODES[case_suffix]
    return {'mode_request': mode,
            'headlamp_low_requested': mode == 'depressed_low_beam',
            'headlamp_high_requested': mode in ('undepressed_high_beam', 'undepressed_high_beam_with_parking'),
            'parking_lamps_requested': mode == 'undepressed_high_beam_with_parking',
            'cowl_lamps_requested': False,
            'optical_state_observed': None,
            'lawfully_parked_observed': None}


def apply_light_request(vehicle, carla, case_suffix, frame):
    request = light_request(case_suffix, frame)
    state = carla.VehicleLightState
    values = {'depressed_low_beam': state.LowBeam,
              'undepressed_high_beam': state.HighBeam,
              'undepressed_high_beam_with_parking': state.HighBeam | state.Position}
    vehicle.set_light_state(state(values[request['mode_request']]))
    return request
