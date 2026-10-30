"""Lossless, explicit projection of retired source vocabulary into current Core.

Retired labels remain typed source provenance. They never become aliases for
current legal classes or evidence of legal aggregate membership.
"""
import copy

RETIRED_CLASSES = frozenset({
    'animal', 'vending_vehicle', 'low_speed_vehicle', 'other_conveyance',
    'procession_vehicle', 'ridden_or_herded_animal', 'animal_drawn_vehicle',
    'personal_delivery_device', 'mobile_carrying_device', 'animal_or_animal_drawn'})
RETIRED_ATOMS = frozenset('ru.' + name for name in RETIRED_CLASSES) | {'st.turnout', 'sig.signal_arm'}
SOURCE_SCHEMA = 'retained-road-user-classes-v1'


def project_user(user, known):
    observed = user.get('classes')
    unobserved = user.get('unobserved_classes', [])
    unknown = (set(observed or []) | set(unobserved)) - set(known)
    if not unknown:
        return user
    if unknown - RETIRED_CLASSES:
        raise ValueError('Unreviewed source class: ' + str(sorted(unknown - RETIRED_CLASSES)))
    if 'source_classifications' in user:
        raise ValueError('Refusing to overwrite existing source classifications')
    result = copy.deepcopy(user)
    source = {'schema': SOURCE_SCHEMA}
    for key in ('classes', 'unobserved_classes'):
        if key in user:
            source[key] = copy.deepcopy(user[key])
    result['source_classifications'] = source
    positives = [c for c in observed or [] if c in known]
    if observed is not None:
        result['classes'] = positives
    result['unobserved_classes'] = [c for c in unobserved if c in known]
    if set(observed or []) - set(known):
        # The current ontology cannot classify this positive source category.
        # Preserve known positives; all other current classes remain unknown.
        result['classes'] = positives if positives else None
        result['unobserved_classes'] = sorted(set(known) - set(positives))
    if restore_user(result) != user:
        raise ValueError('Source classifications did not round-trip')
    return result


def restore_user(user):
    result = copy.deepcopy(user)
    source = result.pop('source_classifications', None)
    if source is None:
        return result
    if source['schema'] != SOURCE_SCHEMA:
        raise ValueError('Unrecognized source classification schema')
    for key in ('classes', 'unobserved_classes'):
        result.pop(key, None)
        if key in source:
            result[key] = copy.deepcopy(source[key])
    return result


def project_manifest(manifest, known):
    result = copy.deepcopy(manifest)
    retired = {key: value for key, value in result['atoms'].items() if key not in known}
    if set(retired) - RETIRED_ATOMS:
        raise ValueError('Unreviewed source capability: ' + str(sorted(set(retired) - RETIRED_ATOMS)))
    if retired:
        if 'source_capabilities' in result:
            raise ValueError('Refusing to overwrite existing source capabilities')
        result['source_capabilities'] = retired
        result['atoms'] = {key: value for key, value in result['atoms'].items() if key in known}
    for key in known:
        result['atoms'].setdefault(key, 'absent')
    reconstructed = dict(result['atoms'], **result.get('source_capabilities', {}))
    if any(reconstructed.get(k) != v for k, v in manifest['atoms'].items()):
        raise ValueError('Source capabilities did not round-trip')
    return result


def known_classes(library):
    import re
    from .adapter import full_core
    text=(full_core(library)/'Vocab/Ontology/RoadUser.lean').read_text()
    block=text.split('namespace RoadUserClass',1)[1].split('end RoadUserClass',1)[0]
    values=set(re.findall(r'\| "([a-z_]+)" =>',block))
    if not values:
        raise ValueError('No current RoadUserClass codec found')
    return values
