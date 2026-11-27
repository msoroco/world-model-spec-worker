"""Engineering crossing-completion probe; never an immediate-hazard legal test."""

from __future__ import annotations

import math


def assess(rows, site, expected_frames=900):
    if (not isinstance(rows, list) or len(rows) != expected_frames or
            not isinstance(site, dict) or site.get('control') != 'stop_sign' or
            site.get('stop_line_present') is not False or
            site.get('near_crosswalk_present') is not False):
        return {'status': 'unverified', 'reason': 'source-bound stop frame/site context missing'}
    occupancy = []
    for i, row in enumerate(rows):
        if (not isinstance(row, dict) or type(row.get('frame')) is not int or
                row['frame'] != i or type(row.get('time_s')) not in (int, float) or
                not math.isfinite(row['time_s']) or
                abs(row['time_s'] - i / 20) > .002 or
                type(row.get('ego_within_intersection')) is not bool):
            return {'status': 'unverified', 'reason': 'original crossing frame/time or occupancy missing'}
        occupancy.append(row['ego_within_intersection'])
    if occupancy[0]:
        return {'status': 'unverified', 'reason': 'approach-before-entry frame missing'}
    active = [i for i, present in enumerate(occupancy) if present]
    if not active:
        return {'status': 'not_met', 'reason': 'no observed intersection entry'}
    if active != list(range(active[0], active[-1]+1)) or active[-1] == len(rows)-1:
        return {'status': 'not_met', 'reason': 'no complete contiguous crossing and exit'}
    return {'status': 'met', 'entry_frame': active[0], 'exit_frame': active[-1]+1,
            'crossing_frames': len(active),
            'reason': 'original body occupancy shows entry and exit; legal stoping unresolved'}
