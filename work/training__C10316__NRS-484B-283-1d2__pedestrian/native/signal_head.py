"""Resolve and sample the authored pedestrian head from Native actors.

Native state readback establishes a device state, not the displayed symbol,
governing direction, or absence of a visible countdown. Those need the
independent original-pixel review after capture.
"""

OPENDRIVE_ID = '203'
DEVICE_ID = 'C10316-authored-pedestrian-head-east'


def resolve(actors):
    matches = []
    for actor in actors:
        if not str(getattr(actor, 'type_id', '')).startswith('traffic.traffic_light'):
            continue
        get_id = getattr(actor, 'get_opendrive_id', None)
        if get_id is not None and str(get_id()) == OPENDRIVE_ID:
            matches.append(actor)
    if len(matches) != 1:
        raise ValueError('Exactly one authored Native pedestrian head required')
    return matches[0]


def command_and_sample(actor, carla, proposed, illuminated):
    expected = ('Green' if proposed == 'walk' else
                'Red' if illuminated else 'Off')
    actor.set_state(getattr(carla.TrafficLightState, expected))
    actor.freeze(True)
    return sample(actor, proposed, illuminated)


def sample(actor, proposed, illuminated):
    expected = ('Green' if proposed == 'walk' else
                'Red' if illuminated else 'Off')
    raw = str(actor.get_state()).split('.')[-1]
    if raw != expected:
        raise ValueError('Native pedestrian head state differs from requested phase')
    if str(actor.get_opendrive_id()) != OPENDRIVE_ID:
        raise ValueError('Native pedestrian head source identity changed')
    return {'device_id': DEVICE_ID, 'opendrive_id': OPENDRIVE_ID,
            'native_actor_id': actor.id, 'native_state': raw,
            'source': 'native_actor_readback',
            'requested_indication': proposed,
            'requested_illumination': illuminated}
