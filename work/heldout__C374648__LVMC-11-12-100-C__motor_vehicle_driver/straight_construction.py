"""Connected straight routes for center-lane-use controls.

The map candidate remains a marking/topology candidate. It does not establish
legal designation or actual straight travel.
"""

from math import degrees, pi

from center_turn_construction import _driving, _heading, _xy


def straight_route(selection, *, origin='center', spacing_m=2.):
    if origin not in ('center', 'outer') or spacing_m <= 0:
        raise ValueError('Invalid straight route origin or spacing')
    chain = selection['center_approach' if origin == 'center' else 'outer_approach']
    approach = chain[-1]
    choices = []
    for junction in approach.next(spacing_m):
        if not _driving(junction) or not junction.is_junction:
            continue
        for exit_wp in junction.next(8.):
            if not _driving(exit_wp) or exit_wp.is_junction:
                continue
            delta = degrees((_heading(exit_wp)-_heading(approach)+pi) % (2*pi)-pi)
            if abs(delta) <= 20:
                choices.append((abs(delta), int(exit_wp.road_id),
                                int(exit_wp.lane_id), junction, exit_wp))
    if len(choices) != 1:
        raise ValueError('Straight route needs one connected heading-consistent exit')
    _, _, _, junction, exit_wp = choices[0]
    targets = [list(_xy(wp)) for wp in chain]
    targets.extend((list(_xy(junction)), list(_xy(exit_wp))))
    return {'targets': targets, 'junction': junction, 'exit': exit_wp,
            'origin': origin, 'designation_authority_verified': False}
