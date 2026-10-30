"""Evidence-preserving checks for the refined road-structure contract.

These checks supplement, and never replace, the complete Lean decoder. Missing
associations remain unknown; geometry proximity is not association evidence.
"""
import math

PARENTS = {'turn_lane': 'lane', 'reserved_lane': 'lane',
           'centre_turn_lane': 'lane', 'one_way_roadway': 'roadway'}
LANES = {'lane', 'turn_lane', 'reserved_lane', 'centre_turn_lane'}
GOVERNABLE = LANES | {'bicycle_lane_or_path', 'roadway', 'one_way_roadway',
                      'shoulder', 'intersection'}


def refines(actual, requested):
    return actual == requested or PARENTS.get(actual) == requested


def kind_value(region, requested):
    """Three-valued kind query; positive refinement is known even if flagged."""
    if refines(region['kind'], requested):
        return True
    if any(refines(requested, unknown)
           for unknown in region.get('unobserved_kinds', [])):
        return None
    return False


def direction(value, place):
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(x, bool) or not isinstance(x, (int, float))
                   or not math.isfinite(x) for x in value)
            or not any(x != 0 for x in value)):
        raise ValueError('Invalid nonzero direction at ' + place)


def validate(scene):
    """Validate only the updated contract, without claiming full-Core validity."""
    regions = {r['id']: r for r in scene.get('structures', [])}
    for user in scene.get('users', []):
        heading = user.get('kin', {}).get('heading')
        if heading is not None:
            direction(heading, 'user heading')
    for region in regions.values():
        vector = (region.get('lane') or {}).get('direction')
        if vector is not None:
            direction(vector, 'region direction')
        association = region.get('entrance_of')
        if association is None:
            continue
        if region['kind'] not in {'stop_line', 'crosswalk'}:
            raise ValueError('entrance_of on unsupported region kind')
        if not isinstance(association, list) or any(
                isinstance(r, bool) or not isinstance(r, int) for r in association):
            raise ValueError('entrance_of must be a list of lane IDs')
        if len(set(association)) != len(association):
            raise ValueError('Duplicate entrance association')
        for target in association:
            if target not in regions or regions[target]['kind'] not in LANES:
                raise ValueError('entrance_of must name an existing lane')
    for device in scene.get('devices', []):
        targets = device.get('governs')
        if targets is None:
            continue
        if not isinstance(targets, list):
            raise ValueError('governs must be an optional list')
        for target in targets:
            if target not in regions or regions[target]['kind'] not in GOVERNABLE:
                raise ValueError('Unsupported governs target')


def remap_regions(scene, replacements):
    """Relink every region-ID field; never rewrite track or device IDs."""
    import copy
    result = copy.deepcopy(scene)
    def mapped(value):
        while value in replacements:
            value = replacements[value]
        return value
    result['structures'] = [r for r in result.get('structures', []) if r['id'] not in replacements]
    for region in result['structures']:
        for key in ('ways', 'entrance_of'):
            if region.get(key) is not None:
                region[key] = list(dict.fromkeys(mapped(r) for r in region[key]))
        lane = region.get('lane') or {}
        for key in ('left', 'right', 'enters_intersection'):
            if lane.get(key) is not None:
                lane[key] = mapped(lane[key])
        if lane.get('leads_to') is not None:
            lane['leads_to'] = list(dict.fromkeys(mapped(r) for r in lane['leads_to']))
    for device in result.get('devices', []):
        if device.get('governs') is not None:
            device['governs'] = list(dict.fromkeys(mapped(r) for r in device['governs']))
    if 'occupies' in result:
        result['occupies'] = [list(pair) for pair in dict.fromkeys(
            (track, mapped(region)) for track, region in result['occupies'])]
    for intent in result.get('intents', []):
        intent['target'] = mapped(intent['target'])
    for user in result.get('users', []):
        if user.get('sight_along_way') is not None:
            user['sight_along_way'] = [[mapped(r), distance] for r, distance in user['sight_along_way']]
    return result
