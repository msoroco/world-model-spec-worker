"""Find a Native stop-sign actor whose trigger contains the approach point.

This tests physical sign governance. Official status and properly erected face
still need Native map and original-camera review.
"""


def find_governing_stop_sign(world, approach_waypoint):
    point = approach_waypoint.transform.location
    matches = []
    for sign in world.get_actors().filter("traffic.stop*"):
        if sign.trigger_volume.contains(point, sign.get_transform()):
            matches.append(sign)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing stop sign, found {len(matches)}")
    return matches[0]
