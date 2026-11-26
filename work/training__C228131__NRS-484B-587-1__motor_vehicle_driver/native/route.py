"""Controller requests for an entrance crossing at the indicated point or 60 m away."""
FRAMES = 600
RATE_HZ = 20
CROSSING_X = {'witness_1': 0.0, 'witness_2': 60.0}


def target(mode, frame):
    if mode not in CROSSING_X or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Unknown controlled-entry target')
    t = frame / RATE_HZ
    crossing_x = CROSSING_X[mode]
    progress = min(1.0, t / 24)
    x = crossing_x - 20 + 40 * progress
    y = -9 + 9 * progress
    return {'x_m': x, 'y_m': y, 'target_speed_mps': 2.0,
            'requested_crossing_x_m': crossing_x,
            'reference_frame': 'authored frontage to highway edge'}
