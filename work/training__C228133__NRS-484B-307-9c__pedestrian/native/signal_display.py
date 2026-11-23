"""Visible red disc and right-turn-arrow staging geometry for Native capture.

Debug geometry is a visual construction proposal. It is never, by itself, an
official governing signal. Original camera pixels and governance require review.
"""

import math


def segments():
    """Return named line segments in a vertical display plane (u, z metres)."""
    lines = []
    red_center = (0.0, 0.28)
    radius = 0.18
    for index in range(16):
        a = 2 * math.pi * index / 16
        b = 2 * math.pi * (index + 1) / 16
        start = (red_center[0] + radius * math.cos(a),
                 red_center[1] + radius * math.sin(a))
        end = (red_center[0] + radius * math.cos(b),
               red_center[1] + radius * math.sin(b))
        lines.append(('red', start, end))
        lines.append(('red', red_center, start))
    lines.extend((
        ('green', (-0.23, -0.22), (0.22, -0.22)),
        ('green', (0.22, -0.22), (0.07, -0.07)),
        ('green', (0.22, -0.22), (0.07, -0.37)),
    ))
    return lines


def draw(world, carla, center, horizontal):
    """Draw the proposal for one Native tick before acquiring camera pixels."""
    colors = {'red': carla.Color(255, 0, 0),
              'green': carla.Color(0, 255, 0)}
    for name, (u0, z0), (u1, z1) in segments():
        begin = carla.Location(x=center.x + u0 * horizontal.x,
                               y=center.y + u0 * horizontal.y,
                               z=center.z + z0)
        end = carla.Location(x=center.x + u1 * horizontal.x,
                             y=center.y + u1 * horizontal.y,
                             z=center.z + z1)
        world.debug.draw_line(begin, end, thickness=0.06,
                              color=colors[name], life_time=0.1,
                              persistent_lines=False)
