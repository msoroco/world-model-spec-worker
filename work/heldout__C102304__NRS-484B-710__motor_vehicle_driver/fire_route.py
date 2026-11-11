"""Select and verify a Native hill-crest following route before actor spawn.

The 500 ft command needs more than 152.4 m of same-lane road.  Selection uses
Native waypoints, including grade, and refuses to relabel a flat road a crest.
"""
from __future__ import annotations

from math import hypot, isfinite


FEET_PER_METRE = 3.280839895013123


def _xy(waypoint):
    p = waypoint.transform.location
    return float(p.x), float(p.y), float(p.z)


def _lane(waypoint):
    return waypoint.road_id, waypoint.section_id, waypoint.lane_id


def route_from(start, *, target_gap_ft=500, step_m=5, runout_m=35):
    """Follow one connected lane and return an ego/apparatus crest pair.

    The selected pair has a centre separation beyond the requested body gap;
    the exact initial body gap is measured after actors are spawned.  Waypoint
    pitch is only a construction cue, never a visibility measurement.
    """
    if not isfinite(target_gap_ft) or target_gap_ft <= 0 or step_m <= 0:
        raise ValueError("Invalid route length or sampling step")
    needed = target_gap_ft / FEET_PER_METRE + runout_m
    chain = [start]
    distance = 0.0
    while distance < needed + 20:
        choices = [w for w in chain[-1].next(step_m)
                   if w.road_id == start.road_id and w.lane_id == start.lane_id
                   and not w.is_junction]
        if len(choices) != 1:
            raise ValueError("Following route needs one continuous nonjunction lane")
        next_waypoint = choices[0]
        a, b = _xy(chain[-1]), _xy(next_waypoint)
        segment = hypot(b[0] - a[0], b[1] - a[1])
        if segment < step_m * .5 or segment > step_m * 1.6:
            raise ValueError("Following route has a discontinuous lane sample")
        distance += segment
        chain.append(next_waypoint)
        if len(chain) > 1000:
            raise ValueError("Following route sample limit exceeded")
    grades = [_xy(chain[i + 1])[2] - _xy(chain[i])[2]
              for i in range(len(chain) - 1)]
    # Both sides of the crest must show at least 0.3 m change over three
    # samples. This is a map-shape check, not an evidentiary sight-line test.
    crest = next((i for i in range(3, len(chain) - 4)
                  if sum(grades[i-3:i]) > .3 and sum(grades[i:i+3]) < -.3), None)
    if crest is None:
        raise ValueError("Native lane has no measured hill crest")
    separation = target_gap_ft / FEET_PER_METRE
    apparatus_index = next((i for i, w in enumerate(chain)
                            if hypot(_xy(w)[0] - _xy(start)[0],
                                     _xy(w)[1] - _xy(start)[1]) >= separation), None)
    if apparatus_index is None or not (2 < crest < apparatus_index - 2):
        raise ValueError("Hill crest does not lie between following actors")
    return {"ego": start, "apparatus": chain[apparatus_index],
            "crest": chain[crest], "chain": chain,
            "road_id": start.road_id, "lane_id": start.lane_id,
            "sampled_distance_m": distance,
            "centre_separation_m": hypot(_xy(chain[apparatus_index])[0] - _xy(start)[0],
                                         _xy(chain[apparatus_index])[1] - _xy(start)[1])}


def select_crest_route(world_map, *, target_gap_ft=500, step_m=5):
    failures = []
    for spawn in world_map.get_spawn_points():
        waypoint = world_map.get_waypoint(spawn.location)
        if waypoint is None or waypoint.is_junction:
            continue
        try:
            return route_from(waypoint, target_gap_ft=target_gap_ft, step_m=step_m)
        except ValueError as error:
            failures.append(str(error))
    raise ValueError("No Native hill-crest route supports the following construction: "
                     + "; ".join(sorted(set(failures))))
