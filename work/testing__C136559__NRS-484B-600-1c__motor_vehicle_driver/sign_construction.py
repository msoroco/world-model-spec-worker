"""Select a Native speed-limit sign by physical trigger and posted-value type."""


def find_governing_speed_sign(world, approach_waypoint, posted_value):
    point = approach_waypoint.transform.location
    matches = []
    for sign in world.get_actors().filter("traffic.speed_limit*"):
        suffix = sign.type_id.rsplit(".", 1)[-1]
        if suffix.isdigit() and int(suffix) == posted_value and sign.trigger_volume.contains(point, sign.get_transform()):
            matches.append(sign)
    if len(matches) != 1:
        raise ValueError(f"Expected one matching governing speed-limit sign, found {len(matches)}")
    return matches[0]
