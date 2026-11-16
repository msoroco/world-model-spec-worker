"""Derive a passenger approach event from retained walker and bus positions.

The event records proximity and movement for later visual review. It does not
establish that a passenger boarded or that a statutory exception applies.
"""
from math import hypot, isfinite


def derive(walker_rows, ego_rows, first_stationary_frame):
    if type(first_stationary_frame) is not int or first_stationary_frame < 0 or \
            len(walker_rows) != len(ego_rows) or not walker_rows:
        raise ValueError('Missing synchronized passenger source rows')
    kind = ego_rows[0].get('source_kind')
    first = last = None
    previous_distance = None
    moved_toward_bus = False
    for i, (walker, ego) in enumerate(zip(walker_rows, ego_rows)):
        if walker.get('frame') != i or ego.get('frame') != i or \
                walker.get('source_kind') != kind or \
                not str(walker.get('blueprint', '')).startswith('walker.pedestrian.'):
            raise ValueError('Changed passenger actor provenance or frame join')
        location = walker.get('center_native_xy_m')
        bus = ego.get('ego_center_native_xy_m')
        if not (isinstance(location, list) and len(location) == 2 and
                isinstance(bus, list) and len(bus) == 2 and
                all(type(value) in (int, float) and isfinite(value)
                    for value in location + bus)):
            raise ValueError('Missing Native passenger or bus position')
        distance = hypot(location[0] - bus[0], location[1] - bus[1])
        if i >= first_stationary_frame:
            if first is None and distance <= 3:
                first = ego['time_s']
                previous_distance = distance
            elif first is not None and last is None:
                if distance < previous_distance - .01:
                    moved_toward_bus = True
                previous_distance = distance
                if moved_toward_bus and distance <= 2:
                    last = ego['time_s']
        if last is not None:
            break
    if first is None or last is None or last <= first:
        raise ValueError('No measured passenger approach at stopped bus')
    return [{'source_kind': kind, 'name': 'passenger_loading',
             'start_time_s': first, 'end_time_s': last,
             'source': 'native-passenger-actors.jsonl: moving walker approached bus; boarding unverified'}]
