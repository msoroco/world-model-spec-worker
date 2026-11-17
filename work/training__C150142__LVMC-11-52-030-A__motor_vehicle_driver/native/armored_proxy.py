"""Construct a visible armored-van proxy; legal vehicle identity stays unverified.

The base van and attached box panels are a capture request.  Neither the
blueprint name nor the panels prove that a vehicle is an armored car.
"""

BASE_BLUEPRINT = 'vehicle.mercedes.sprinter'
PANEL_BLUEPRINT = 'static.prop.box01'
PANELS = (
    ('left_side', (0.0, -1.12, 1.65), (0, 0, 0)),
    ('right_side', (0.0, 1.12, 1.65), (0, 0, 0)),
    ('rear', (-2.5, 0.0, 1.65), (0, 0, 90)),
    ('roof', (0.0, 0.0, 2.55), (0, 0, 0)),
)


def validate(config):
    if config.get('native_blueprint') != BASE_BLUEPRINT or \
       config.get('service_class') != 'armored_car' or \
       config.get('armor_proxy_kind') != 'attached_box_panels_v1' or \
       config.get('armor_panel_blueprint') != PANEL_BLUEPRINT:
        raise ValueError('Armored visual proxy construction differs')
    return True


def spawn(world, library, carla, ego, config):
    """Attach four requested armor panels and return owned actors/readback.

    A CARLA build lacking the specified prop fails explicitly, preserving the
    request and allowing an asset-backed replacement in the next candidate.
    """
    validate(config)
    blueprint = library.find(PANEL_BLUEPRINT)
    owned = []
    readback = []
    for name, location, rotation in PANELS:
        transform = carla.Transform(carla.Location(*location),
                                    carla.Rotation(*rotation))
        actor = world.try_spawn_actor(blueprint, transform, attach_to=ego)
        if actor is None:
            for prior in reversed(owned):
                prior.destroy()
            raise RuntimeError('Armored proxy panel spawn failed: ' + name)
        owned.append(actor)
        readback.append({'name': name, 'actor_id': actor.id,
                         'blueprint': actor.type_id,
                         'relative_location_m': list(location),
                         'relative_rotation_deg': list(rotation)})
    return owned, readback


def verify_readback(data, actor_rows, config):
    """Bind the panel request to retained Native actor IDs and poses."""
    validate(config)
    if data.get('source_kind') not in ('native_readback', 'synthetic_native_sample') or \
       data.get('legal_armored_identity_verified') is not False or \
       data.get('base_blueprint') != BASE_BLUEPRINT or \
       not actor_rows or data.get('base_actor_id') != actor_rows[0].get('actor_id'):
        raise ValueError('Missing source-bound armored proxy base readback')
    panels = data.get('panels')
    if not isinstance(panels, list) or len(panels) != len(PANELS):
        raise ValueError('Missing source-bound armored proxy panels')
    ids = set()
    for panel, (name, location, rotation) in zip(panels, PANELS):
        if panel.get('name') != name or \
           panel.get('blueprint') != PANEL_BLUEPRINT or \
           panel.get('relative_location_m') != list(location) or \
           panel.get('relative_rotation_deg') != list(rotation) or \
           not isinstance(panel.get('actor_id'), int) or \
           panel['actor_id'] in ids or panel['actor_id'] == data['base_actor_id']:
            raise ValueError('Armored proxy panel readback differs: ' + name)
        ids.add(panel['actor_id'])
    return {'base_blueprint': BASE_BLUEPRINT, 'panels_observed': len(panels),
            'legal_armored_identity_verified': False}
