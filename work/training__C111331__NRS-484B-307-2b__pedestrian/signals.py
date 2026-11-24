"""Resolve authored OpenDRIVE heads to original Native signal actors.

The state readback is not a pixel or legal-governance finding. Missing or
ambiguous actors fail closed instead of using requested phase declarations.
"""

HEADS = {'traffic': ('201', 'C111331-facing-circular-head'),
         'pedestrian': ('202', 'C111331-governing-pedestrian-head')}


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
    if set(found) != set(HEADS) or found['traffic'].id == found['pedestrian'].id:
        raise ValueError('Both distinct Native OpenDRIVE signal actors required')
    return found


def sample(heads):
    values = {}
    for role, actor in heads.items():
        raw = str(actor.get_state()).split('.')[-1].lower()
        states = ({'green': 'circular_green', 'yellow': 'circular_yellow',
                   'red': 'circular_red'} if role == 'traffic' else
                  {'green': 'walk', 'red': 'dont_walk', 'off': 'dark'})
        if raw not in states:
            raise ValueError('Unrecognized Native signal state: ' + role + '=' + raw)
        values[role] = {'id': HEADS[role][1], 'opendrive_id': HEADS[role][0],
                        'native_actor_id': actor.id, 'raw_state': raw,
                        'state': states[raw], 'source': 'native_readback'}
    return values


def configure(heads, requested_pedestrian_indication, carla):
    """Set both authored heads and verify original Native state readback."""
    if requested_pedestrian_indication not in ('walk', 'dont_walk'):
        raise ValueError('Unknown requested pedestrian indication')
    expected = {'traffic': 'circular_green',
                'pedestrian': requested_pedestrian_indication}
    states = {'traffic': carla.TrafficLightState.Green,
              'pedestrian': (carla.TrafficLightState.Green
                             if requested_pedestrian_indication == 'walk'
                             else carla.TrafficLightState.Red)}
    for role, actor in heads.items():
        actor.set_state(states[role])
        actor.freeze(True)
    observed = sample(heads)
    if {role: value['state'] for role, value in observed.items()} != expected:
        raise ValueError('Native signal state readback differs from authored request')
    return observed
