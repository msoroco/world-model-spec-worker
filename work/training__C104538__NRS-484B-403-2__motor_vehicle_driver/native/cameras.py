"""Four synchronized original-pixel capture requests; coverage needs GPU review."""

PROFILE = 'overview1080-signed-u-turn-proposal-v1'
RATE_HZ = 20


def camera_plan(candidate_id):
    if candidate_id not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown signed-road candidate')
    sign_xyz = [-12, 11, 6] if candidate_id == 'fallback3' else [-12, 9, 5]
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 75,
         'attachment': 'world', 'xyz_m': [5, 24, 40], 'pitch_deg': -63,
         'purpose': 'hill approach, sign region, entire requested movement'},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 92,
         'attachment': 'ego', 'xyz_m': [-9, 0, 4], 'pitch_deg': -15,
         'purpose': 'complete ego body and approach lane; original pixel source'},
        {'name': 'sign_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'attachment': 'world', 'xyz_m': sign_xyz, 'pitch_deg': -22,
         'purpose': 'physical prohibition cue and governed approach'},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 105,
         'attachment': 'ego', 'xyz_m': [1, 0, 1.5], 'pitch_deg': -2,
         'purpose': 'forward context; does not prove driver perception'},
    ]
