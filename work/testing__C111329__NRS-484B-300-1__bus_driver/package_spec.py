"""Exact source-gated bus/device case and recording contract."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = 'testing__C111329__NRS-484B-300-1__bus_driver'
LAW = 'NRS-484B-300-1'
CELL = 'C111329'
ACTOR = 'bus_driver'
CASES = (
    ('red_hold', 'red', 'hold_red', None, False),
    ('red_enter', 'red', 'enter_red', None, True),
    ('red_police_proceed', 'red', 'follow_police', 'proceed', True),
    ('green_proceed', 'green', 'proceed_when_green', None, True),
)
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [
    {'name': name, 'width': 1920 if index == 0 else 1280,
     'height': 1080 if index == 0 else 720, 'fov_deg': 75,
     'pose_strategy': 'reviewed bus route, governing device and surveyed stop line'}
    for index, name in enumerate(CAMERA_NAMES)
]
CHANNELS = (
    ('device_aspect', 'source record', 'original governing signal aspect and frame'),
    ('bus_front_line_distance_m', 'm', 'original bus front signed distance to surveyed stop line'),
    ('police_direction', 'source record', 'contemporaneous original officer direction and provenance'),
    ('official_placement', 'source record', 'original device provenance and placement review'),
    ('nrs_307_context', 'source record', 'original device-specific exception context'),
    ('camera_frame_identity', 'frame ID', 'four synchronized original camera streams'),
)
RECORDING = {
    'channels': [
        {'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20,
         'time_window': '45-second intersection approach',
         'reference_frame': 'source-sealed original Native frame/time',
         'uncertainty': 'original source and physical realization require local review'}
        for name, unit, method in CHANNELS
    ],
    'context_inputs': [
        {'name': 'reviewed_device_site_packet', 'unit': 'source record',
         'method': 'source-hashed map, device, route, line, authority and 307 context'}
    ],
    'limitations': [
        'Synthetic fixture verifies software contracts only.',
        'Official placement, police authority, 307 applicability and legal compliance remain unresolved.'
    ],
}


def case_id(name):
    return AID + '__' + name
