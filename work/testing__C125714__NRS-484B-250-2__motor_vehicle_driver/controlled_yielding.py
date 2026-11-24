"""C125714 controlled ego policy; actual yielding remains a saved-source judgment."""
from __future__ import annotations

from entry_timing import intersects, polygon

POLICIES = ('timed_release', 'wait_for_other_clear', 'advance_at_release')


class Controller:
    def __init__(self, policy, crossing_polygon, ego_release_s, other_release_s):
        if policy not in POLICIES:
            raise ValueError('unknown exact ego controller policy')
        if ego_release_s < 0 or other_release_s < 0:
            raise ValueError('nonnegative original release schedule required')
        self.policy = policy
        self.crossing = polygon(crossing_polygon)
        self.ego_release_s = ego_release_s
        self.other_release_s = other_release_s
        self.other_entered = False
        self.other_cleared = False

    def update_other(self, body_vertices_xy_m):
        inside = intersects(polygon(body_vertices_xy_m), self.crossing)
        if inside:
            self.other_entered = True
        elif self.other_entered:
            self.other_cleared = True
        return inside

    def controls(self, elapsed_s):
        if elapsed_s < 0:
            raise ValueError('original Native elapsed time required')
        other_go = elapsed_s >= self.other_release_s
        ego_go = elapsed_s >= self.ego_release_s
        if self.policy == 'wait_for_other_clear':
            ego_go = ego_go and self.other_cleared
        # The advance policy applies throttle at its authored release even when
        # the other actor has entered. It does not assert a legal outcome.
        return {'ego': {'throttle': .35 if ego_go else 0.0,
                        'brake': 0.0 if ego_go else 1.0},
                'other': {'throttle': .35 if other_go else 0.0,
                          'brake': 0.0 if other_go else 1.0}}
