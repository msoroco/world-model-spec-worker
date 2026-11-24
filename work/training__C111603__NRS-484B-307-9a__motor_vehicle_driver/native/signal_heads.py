"""Bind the two authored OpenDRIVE heads to distinct Native light actors."""

HEAD_IDS = {'red': '601', 'arrow': '1603'}


def resolve(actors):
    found = {}
    for actor in actors:
        if not str(getattr(actor, 'type_id', '')).startswith('traffic.traffic_light'):
            continue
        read_id = getattr(actor, 'get_opendrive_id', None)
        if not callable(read_id):
            continue
        source_id = str(read_id())
        for name, expected in HEAD_IDS.items():
            if source_id == expected:
                if name in found:
                    raise ValueError('Ambiguous authored Native signal head: ' + name)
                found[name] = actor
    if set(found) != set(HEAD_IDS) or found['red'].id == found['arrow'].id:
        raise ValueError('Both distinct authored Native signal heads required')
    return found['red'], found['arrow']


def sample(red, arrow):
    states = {'red': str(red.get_state()).split('.')[-1].lower(),
              'arrow': str(arrow.get_state()).split('.')[-1].lower()}
    if states != {'red': 'red', 'arrow': 'green'}:
        raise ValueError('Native authored head states differ from red plus green request')
    return {'red': {'opendrive_id': HEAD_IDS['red'], 'actor_id': red.id,
                    'state': states['red'], 'source': 'native_readback'},
            'arrow': {'opendrive_id': HEAD_IDS['arrow'], 'actor_id': arrow.id,
                      'state': states['arrow'], 'source': 'native_readback'}}
