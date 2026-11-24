"""Validate source-shaped rotary body corners against recorded ego pose.

The present 2.0 m by 0.9 m half extents belong to synthetic diagnostics only.
Original Native review must supply its own vehicle bounding-box extents.
"""
import math


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate(rows, half_length_m, half_width_m):
    require(len(rows) == 240, 'Rotary body interval must have 240 frames')
    require(all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value > 0
                for value in (half_length_m, half_width_m)),
            'Body extents must be positive source measurements')
    source_kind = rows[0].get('source_kind')
    require(source_kind in ('synthetic_cpu', 'original_native'),
            'Rotary body source kind unresolved')
    for index, row in enumerate(rows):
        require(row.get('frame') == index
                and row.get('source_kind') == source_kind,
                'Rotary body frame or provenance differs at ' + str(index))
        x, y, heading = (row.get(key) for key in
                         ('ego_x_m', 'ego_y_m', 'ego_heading_deg'))
        require(all(isinstance(value, (int, float))
                    and not isinstance(value, bool) and math.isfinite(value)
                    for value in (x, y, heading)),
                'Rotary body pose invalid at ' + str(index))
        angle = math.radians(heading)
        forward = math.cos(angle), math.sin(angle)
        left = -forward[1], forward[0]
        expected = [[x + dx * forward[0] + dy * left[0],
                     y + dx * forward[1] + dy * left[1]]
                    for dx, dy in ((-half_length_m, -half_width_m),
                                   (-half_length_m, half_width_m),
                                   (half_length_m, half_width_m),
                                   (half_length_m, -half_width_m))]
        body = row.get('ego_body_xy_m')
        require(isinstance(body, list) and len(body) == 4,
                'Rotary body corner inventory differs at ' + str(index))
        for corner, (actual, wanted) in enumerate(zip(body, expected)):
            require(isinstance(actual, list) and len(actual) == 2
                    and all(isinstance(value, (int, float))
                            and not isinstance(value, bool) and math.isfinite(value)
                            for value in actual)
                    and max(abs(actual[0] - wanted[0]),
                            abs(actual[1] - wanted[1])) <= 2e-6,
                    'Rotary body corner differs at ' + str(index)
                    + '/' + str(corner))
    return {'frames_checked': 240, 'corners_checked': 960,
            'source_kind': source_kind,
            'half_length_m': half_length_m,
            'half_width_m': half_width_m}
