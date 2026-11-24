"""Resolve two authored heads to original Native actors and read raw states.

CARLA's generic Green state does not establish a green turn arrow alone.
"""

HEADS = {'arrow': ('201', 'C111334-facing-green-turn-arrow'),
         'other': ('202', 'C111334-other-permitting-device')}


def resolve(actors):
    found = {}
    for actor in actors:
        if not str(getattr(actor, 'type_id', '')).startswith('traffic.traffic_light'):
            continue
        get_id = getattr(actor, 'get_opendrive_id', None)
        if get_id is None:
            continue
        source_id = str(get_id())
        for role, (expected, _) in HEADS.items():
            if source_id == expected:
                if role in found:
                    raise ValueError('Ambiguous Native OpenDRIVE head: ' + role)
                found[role] = actor
    if set(found) != set(HEADS) or found['arrow'].id == found['other'].id:
        raise ValueError('Both distinct Native OpenDRIVE signal actors required')
    return found


def sample(heads):
    values = {}
    for role, actor in heads.items():
        raw = str(actor.get_state()).split('.')[-1].lower()
        if raw not in ('green', 'yellow', 'red', 'off'):
            raise ValueError('Unrecognized Native signal state: ' + role + '=' + raw)
        values[role] = {'id': HEADS[role][1], 'opendrive_id': HEADS[role][0],
                        'native_actor_id': actor.id, 'raw_state': raw,
                        'source': 'native_readback',
                        'turn_arrow_alone_confirmed': False if role == 'arrow' else None,
                        'other_device_permission_confirmed': False if role == 'other' else None}
    return values
