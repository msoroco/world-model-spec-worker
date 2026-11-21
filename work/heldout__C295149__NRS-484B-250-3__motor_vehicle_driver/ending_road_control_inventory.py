"""Conservative Native control inventory for an ending/through route pair.

Landmarks are queried from both original approach lanes. A returned landmark is
treated as potentially governing until a later physical/source review resolves
its authority; an uncontrolled construction must reject that route pair.
"""


def approach_landmarks(path, *, lookahead_m=3.0):
    if not path or path[0].is_junction or not any(p.is_junction for p in path):
        raise ValueError('Control inventory requires an exterior-to-junction route')
    found = {}
    for waypoint in path:
        if waypoint.is_junction:
            break
        query = getattr(waypoint, 'get_landmarks', None)
        if query is None:
            raise ValueError('Native waypoint landmark query unavailable')
        for landmark in query(lookahead_m, stop_at_junction=True):
            ident = str(getattr(landmark, 'id', '') or '').strip()
            kind = str(getattr(landmark, 'type', '') or '').strip()
            if not ident or not kind:
                raise ValueError('Native landmark lacks OpenDRIVE ID or type')
            found[ident] = {'opendrive_id': ident, 'type': kind,
                            'approach_road_id': path[0].road_id,
                            'approach_lane_id': path[0].lane_id}
    return list(found.values())


def ungoverned_route_pair(ending, through, lights):
    """Fail closed on sign/landmark or traffic-light evidence at the junction."""
    from ending_road_device import devices_at_junction

    if devices_at_junction(lights, ending['junction_id']):
        return False
    return not (approach_landmarks(ending['path']) or
                approach_landmarks(through['path']))


def original_ungoverned_inventory(ending, through, lights):
    """Retain the selected Native no-control readback for later comparison.

    Both approach landmark queries and the junction light inventory are repeated
    after route selection, so a route predicate alone cannot stand in for a
    saved original source.
    """
    from ending_road_device import devices_at_junction

    junction_id = ending['junction_id']
    if through['junction_id'] != junction_id:
        raise ValueError('Control inventory routes enter different junctions')
    ending_marks = approach_landmarks(ending['path'])
    through_marks = approach_landmarks(through['path'])
    governing_lights = devices_at_junction(lights, junction_id)
    if ending_marks or through_marks or governing_lights:
        raise ValueError('Selected ordinary route has a potential governing control')
    return {'format': 'worker-ending-road-original-control-inventory',
            'junction_id': junction_id,
            'ending_approach_road_id': ending['path'][0].road_id,
            'ending_approach_lane_id': ending['path'][0].lane_id,
            'through_approach_road_id': through['path'][0].road_id,
            'through_approach_lane_id': through['path'][0].lane_id,
            'ending_landmarks': ending_marks, 'through_landmarks': through_marks,
            'junction_lights': [], 'legal_control_status_claimed': False}
