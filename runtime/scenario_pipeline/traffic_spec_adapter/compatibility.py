"""Evidence-preserving checks for the refined road-structure contract.

These checks supplement, and never replace, the complete Lean decoder. Missing
associations remain unknown; geometry proximity is not association evidence.
"""
import math

PARENTS = {'turn_lane': 'lane', 'reserved_lane': 'lane',
           'centre_turn_lane': 'lane', 'one_way_roadway': 'roadway'}
LANES = {'lane', 'turn_lane', 'reserved_lane', 'centre_turn_lane'}
ENTRANCE_CARRIERS = LANES | {'roadway', 'one_way_roadway', 'shoulder', 'bicycle_lane_or_path'}
GOVERNABLE = LANES | {'bicycle_lane_or_path', 'roadway', 'one_way_roadway',
                      'shoulder', 'intersection'}


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
            if target not in regions or regions[target]['kind'] not in ENTRANCE_CARRIERS:
                raise ValueError('entrance_of must name an existing directed carrier')
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
    present={r['id'] for r in scene.get('structures',[])}
    def mapped(value):
        seen=set()
        while value in replacements:
            if value in seen:raise ValueError('Cyclic region replacement')
            seen.add(value);value=replacements[value]
        if seen and value not in present:raise ValueError('Region replacement has no surviving target')
        return value
    for value in replacements:mapped(value)
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
    if 'intents' in result:
        from context_catalogue import remap_intention_targets
        result['intents']=remap_intention_targets(result['intents'],replacements)
        pairs=[(record.get('vehicle'),record['target']) for record in result['intents']]
        if len(pairs)!=len(set(pairs)):
            raise ValueError('Conflicting remapped intention declarations')
    for user in result.get('users', []):
        if user.get('sight_along_way') is not None:
            distances={}
            for region,distance in user['sight_along_way']:
                target=mapped(region)
                if target in distances and distances[target]!=distance:
                    raise ValueError('Conflicting remapped sight-along-way measurements')
                distances[target]=distance
            user['sight_along_way'] = [[region,distance] for region,distance in distances.items()]
    return result
