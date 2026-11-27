"""CARLA-free candidate rail and curb geometry tests."""

import json
from types import SimpleNamespace as NS

from rail_native_geometry import rail_from_actor, choose_curb_waypoint


def vec(x, y):
    return NS(x=x, y=y)


def actor(actor_id, x):
    pose = NS(transform=lambda p: vec(x + p.x, p.y),
              get_forward_vector=lambda: vec(0, 1),
              get_right_vector=lambda: vec(1, 0))
    return NS(id=actor_id, type_id='static.prop.physical_rail',
              bounding_box=NS(location=vec(0, 0), extent=vec(10, .05)),
              get_transform=lambda: pose)


def waypoint(x):
    pose = NS(location=vec(x, 0), get_forward_vector=lambda: vec(1, 0),
              get_right_vector=lambda: vec(0, -1))
    return NS(lane_id=-1, lane_width=2.5, transform=pose,
              get_right_lane=lambda: NS(lane_type='Sidewalk'))


def main():
    rails = [rail_from_actor(actor(5, 0)), rail_from_actor(actor(6, 1.435))]
    assert len(rails) == 2 and rails[0]['polyline_xy_m'] == [[0, -10], [0, 10]]
    candidates = [waypoint(x) for x in (15.935, 19.935)]
    first = choose_curb_waypoint(candidates, rails, 12.5, 2, 1)
    second = choose_curb_waypoint(candidates, rails, 16.5, 2, 1)
    assert first['waypoint'] is candidates[0] and second['waypoint'] is candidates[1]
    assert abs(first['predicted_footprint_gap_m'] - 12.5) < 1e-8
    assert abs(second['predicted_footprint_gap_m'] - 16.5) < 1e-8
    bad = actor(7, 2)
    bad.bounding_box.extent.y = 1
    try:
        rail_from_actor(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('Wide nonrail geometry accepted')
    try:
        choose_curb_waypoint(candidates, rails, 5, 2, 1)
    except ValueError:
        pass
    else:
        raise AssertionError('Unreachable placement accepted')
    print(json.dumps({'synthetic_geometry': True, 'rail_survey_shape': 2,
                      'curb_targets': [12.5, 16.5], 'negative_count': 2,
                      'native_motion_observed': False}))


if __name__ == '__main__':
    main()
