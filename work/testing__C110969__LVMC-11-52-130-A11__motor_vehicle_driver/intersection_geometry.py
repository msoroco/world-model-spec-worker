"""Offline footprint targets for the C110969 intersection approach.

Coordinates are local east/north metres, with an axis-aligned intersection box.
The target is a requested stopping pose, never an observation of CARLA motion.
"""

from dataclasses import dataclass
from math import cos, hypot, radians, sin


FEET_TO_METRES = 0.3048
STATUTORY_DISTANCE_M = 15 * FEET_TO_METRES


@dataclass(frozen=True)
class Box:
    west: float
    south: float
    east: float
    north: float

    def __post_init__(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("Invalid intersection boundary")


def footprint(cx, cy, heading_deg, length_m, width_m):
    """Four corners of the requested body pose in local map coordinates."""
    if length_m <= 0 or width_m <= 0:
        raise ValueError("Vehicle dimensions must be positive")
    angle = radians(heading_deg)
    fx, fy = cos(angle), sin(angle)
    lx, ly = -fy, fx
    return tuple((cx + a * length_m / 2 * fx + b * width_m / 2 * lx,
                  cy + a * length_m / 2 * fy + b * width_m / 2 * ly)
                 for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1)))


def target_pose(boundary, approach, gap_m, length_m, width_m):
    """Place the front bumper gap_m before the chosen boundary face."""
    if gap_m < 0:
        raise ValueError("Gap cannot be negative")
    if approach == "east":
        return boundary.east + gap_m + length_m / 2, 0.0, 180.0
    if approach == "west":
        return boundary.west - gap_m - length_m / 2, 0.0, 0.0
    if approach == "north":
        return 0.0, boundary.north + gap_m + length_m / 2, 270.0
    if approach == "south":
        return 0.0, boundary.south - gap_m - length_m / 2, 90.0
    raise ValueError("Unknown approach")


def _point_segment_distance(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy)))
    return hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def _inside_convex(point, corners):
    signs = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        if abs(cross) > 1e-9:
            signs.append(cross > 0)
    return not signs or all(sign == signs[0] for sign in signs)


def _segments_intersect(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if not (cross(a, b, c) * cross(a, b, d) <= 0 and
            cross(c, d, a) * cross(c, d, b) <= 0):
        return False
    return (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) and
            max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])))


def polygon_gap_to_boundary(corners, boundary):
    """Minimum body-to-intersection distance for nonoverlapping convex footprints."""
    bx = ((boundary.west, boundary.south), (boundary.east, boundary.south),
          (boundary.east, boundary.north), (boundary.west, boundary.north))
    if any(_inside_convex(p, bx) for p in corners):
        return 0.0
    if any(_inside_convex(p, corners) for p in bx):
        return 0.0
    edges_a = tuple(zip(corners, corners[1:] + corners[:1]))
    edges_b = tuple(zip(bx, bx[1:] + bx[:1]))
    if any(_segments_intersect(a, b, c, d)
           for a, b in edges_a for c, d in edges_b):
        return 0.0
    return min([_point_segment_distance(p, a, b) for p in corners for a, b in edges_b] +
               [_point_segment_distance(p, a, b) for p in bx for a, b in edges_a])


def classify_measured_gap(gap_m):
    """Numeric branch only; neither a legal verdict nor an intent finding."""
    if gap_m < 0:
        raise ValueError("Measured gap cannot be negative")
    if gap_m < STATUTORY_DISTANCE_M:
        return "below_15ft"
    if gap_m == STATUTORY_DISTANCE_M:
        return "at_15ft"
    return "above_15ft"
