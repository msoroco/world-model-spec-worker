"""Four source-camera requests for original Native capture."""


def plan():
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 90,
         'attachment': 'world', 'xyz_m': [-25, -25, 30], 'pitch_deg': -30},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'attachment': 'ego', 'xyz_m': [-9, 0, 4], 'pitch_deg': -12},
        {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 80,
         'attachment': 'world', 'xyz_m': [4, 8, 6], 'pitch_deg': -15},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 100,
         'attachment': 'ego', 'xyz_m': [1, 0, 1.5], 'pitch_deg': -2},
    ]


def check():
    specs = plan()
    if [item['name'] for item in specs] != [
            'overview', 'approach', 'reference_corner', 'driver_reference']:
        raise ValueError('Named four-camera profile changed')
    if [(item['width'], item['height']) for item in specs] != \
            [(1920, 1080)] + [(1280, 720)] * 3:
        raise ValueError('Four-camera dimensions changed')
    return {'camera_count': len(specs), 'named_profile': [item['name'] for item in specs],
            'native_visibility_unverified': True}
