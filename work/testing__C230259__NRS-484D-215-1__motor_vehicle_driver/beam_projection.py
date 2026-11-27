"""Project original CARLA participant geometry into original camera frames.

The result is a proposed pixel ROI bound to original sensor calibration and
body/eye coordinates. It must be reviewed against retained original images
before the ROI source is marked reviewed for saved photometry.
"""
from __future__ import annotations

import math


def _matrix(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 4 or
            any(not isinstance(row, (list, tuple)) or len(row) != 4 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in row)
                for row in value)):
        raise ValueError("original camera inverse 4x4 transform required")
    return value


def project(point, world_to_camera, width: int, height: int, fov_deg: float):
    if (not isinstance(point, (list, tuple)) or len(point) != 3 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in point)):
        raise ValueError("original world point required")
    matrix = _matrix(world_to_camera)
    if (type(width) is not int or type(height) is not int or width < 2 or height < 2 or
            type(fov_deg) not in (int, float) or not 1 <= fov_deg < 179):
        raise ValueError("original camera calibration invalid")
    camera = [sum(matrix[row][column] * (list(point) + [1.0])[column]
                  for column in range(4)) for row in range(3)]
    if camera[0] <= .01:
        raise ValueError("review target is behind original camera")
    focal = width / (2 * math.tan(math.radians(fov_deg) / 2))
    return [width / 2 + focal * camera[1] / camera[0],
            height / 2 - focal * camera[2] / camera[0]]


def bbox(points, world_to_camera, width: int, height: int, fov_deg: float,
         *, margin_px: int = 2):
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError("four original body/eye corner points required")
    if type(margin_px) is not int or margin_px < 0:
        raise ValueError("pixel ROI margin invalid")
    pixels = [project(point, world_to_camera, width, height, fov_deg)
              for point in points]
    left = max(0, math.floor(min(point[0] for point in pixels)) - margin_px)
    top = max(0, math.floor(min(point[1] for point in pixels)) - margin_px)
    right = min(width, math.ceil(max(point[0] for point in pixels)) + margin_px)
    bottom = min(height, math.ceil(max(point[1] for point in pixels)) + margin_px)
    if right - left < 2 or bottom - top < 2:
        raise ValueError("original projected ROI too small or outside frame")
    return [left, top, right, bottom]


def eye_cube(eye_world_m, half_extent_m: float = .18):
    if (not isinstance(eye_world_m, list) or len(eye_world_m) != 3 or
            any(type(x) not in (float, int) or not math.isfinite(x) for x in eye_world_m) or
            type(half_extent_m) not in (float, int) or not 0 < half_extent_m <= .5):
        raise ValueError("original driver-eye source and engineering ROI extent required")
    return [[eye_world_m[0] + dx * half_extent_m,
             eye_world_m[1] + dy * half_extent_m,
             eye_world_m[2] + dz * half_extent_m]
            for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
