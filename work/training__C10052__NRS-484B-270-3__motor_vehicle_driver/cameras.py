"""Four source-camera policies for the proposed facility occupancy capture."""


def camera_plan(candidate):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown C10052 camera policy')
    wide = candidate == 'fallback3'
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080,
         'xyz_m': [-8, -14, 12 if wide else 9],
         'fov_deg': 105 if wide else 90, 'attachment': 'world'},
        {'name': 'approach', 'width': 1280, 'height': 720,
         'xyz_m': [-25, -9, 6], 'fov_deg': 95, 'attachment': 'world'},
        {'name': 'facility', 'width': 1280, 'height': 720,
         'xyz_m': [-12, -13, 10 if wide else 7],
         'fov_deg': 105 if wide else 90, 'attachment': 'world'},
        {'name': 'driver_reference', 'width': 1280, 'height': 720,
         'xyz_m': [1, 0, 2.2], 'fov_deg': 90, 'attachment': 'ego'}]
