"""Direction-aware lateral targets for an unexcepted left-half excursion probe.

Targets are controller requests. Original retained full-body footprints must
measure the realized crossing; this helper makes no physical or legal claim.
"""

from math import hypot


def target_xy(waypoint, *, frame_index, onset_frame=12, ramp_frames=24,
              requested_fraction=0.75):
    """Return a connected route target shifted toward the opposite half.

    `requested_fraction` is a fraction of the subject lane width. It is an
    engineering controller parameter, not a statutory cutoff or observation.
    """
    if frame_index < 0 or onset_frame < 0 or ramp_frames < 1:
        raise ValueError('Invalid excursion timing')
    if not 0 < requested_fraction < 1:
        raise ValueError('Invalid lane-width fraction')
    width = float(waypoint.lane_width)
    if width <= 0:
        raise ValueError('Original route lane width unavailable')
    location = waypoint.transform.location
    forward = waypoint.transform.get_forward_vector()
    norm = hypot(forward.x, forward.y)
    if norm < .8:
        raise ValueError('Original route tangent undefined')
    tx, ty = forward.x / norm, forward.y / norm
    # CARLA's right vector in this road convention is (-ty, tx). The left
    # excursion therefore travels along (ty, -tx) in world XY.
    phase = max(0.0, min(1.0, (frame_index - onset_frame) / ramp_frames))
    offset = requested_fraction * width * phase
    return [location.x + ty * offset, location.y - tx * offset]
