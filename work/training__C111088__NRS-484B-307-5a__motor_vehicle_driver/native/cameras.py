"""Four original source camera proposals, with final pixel adequacy pending."""
from engineering import KNOBS


def camera_plan(candidate_id: str) -> list[dict]:
    if candidate_id not in KNOBS:
        raise ValueError('Unknown candidate')
    fov = KNOBS[candidate_id]['overview_fov_deg']
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': fov,
         'attachment': 'world', 'xyz_m': [20, -24, 40],
         'purpose': 'both signal heads, ego and prior-entered other vehicle'},
        {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'attachment': 'world', 'xyz_m': [9, -24, 14],
         'purpose': 'ego governing head, stop line and crosswalk'},
        {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 85,
         'attachment': 'ego', 'xyz_m': [1, 0, 1.7],
         'purpose': 'ego facing sole straight-arrow aspect'},
        {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
         'attachment': 'world', 'xyz_m': [-18, 9, 12],
         'purpose': 'prior west entry and intersection occupancy'},
    ]
