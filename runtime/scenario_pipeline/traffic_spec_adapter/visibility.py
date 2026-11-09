"""Subject-relative regional sight distance from declared any-body measurements.

The scalar is a conservative sampled minimum across all inventoried approaches,
not a physical cutoff when the search is censored. Detailed rays remain in the
supplement. Never substitute centre horizons or infer a horizon from one probe.
"""
import math

CONVENTION = 'incoming driving-lane waypoint arc length to actor projected station'


def sight_distance(visibility):
    """Return (metres, reason). Unknown coverage/geometry yields no scalar."""
    if not visibility or visibility.get('visibility_criterion') != 'any_of_nine_body_samples':
        return None, 'any-body horizons not captured'
    if visibility.get('distance_convention') != CONVENTION or visibility.get('unknown_reason'):
        return None, 'unknown visibility geometry or distance convention'
    for key in ('eye_height_m', 'scan_step_m', 'horizon_tolerance_m', 'probe_distance_m'):
        value = visibility.get(key)
        if value is None:
            return None, 'missing declared visibility convention: '+key
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid visibility convention: '+key)
    points = visibility.get('ego_body_samples_m', [])
    if len(points) != 9:
        return None, 'nine measured body targets unavailable'
    if any(not isinstance(p, (list, tuple)) or len(p) != 3 or
           any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Invalid visibility body samples')
    probe = visibility['probe_distance_m']
    required = visibility.get('required_lane_ids', [])
    approaches = visibility.get('approaches', [])
    ids = [a.get('lane_id') for a in approaches]
    if not required or len(ids) != len(set(ids)) or set(ids) != set(required):
        return None, 'incomplete approach coverage'
    bounds = []
    for approach in approaches:
        h = approach.get('any_body_sight_horizon', {})
        if approach.get('unknown_reason') or h.get('unknown'):
            return None, 'missing or ambiguous approach route'
        if h.get('bound') == 'first_sampled_occlusion':
            bracket = h.get('bracket_m', [])
            if len(bracket) != 2:
                return None, 'missing visibility bracket'
            low, high = bracket
            tolerance = visibility.get('horizon_tolerance_m')
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) for v in (low, high)) or not 0 <= low <= high:
                raise ValueError('Invalid visibility bracket')
            if tolerance is None or high-low > tolerance+1e-9:
                return None, 'unrefined visibility bracket'
            if low < probe <= high and not (high == probe and approach.get('any_sample_clear_at_probe') is False):
                return None, 'visibility bracket straddles declared probe'
            value = low  # Clear-side bound, never the uncertain midpoint.
        elif h.get('bound') == 'at_least':
            value = h.get('distance_m')
            # Do not use an unfinished search to classify the declared probe.
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid visibility search bound')
            if value < probe:
                return None, 'censored search shorter than declared probe'
        else:
            return None, 'unknown horizon bound'
        if value >= probe and approach.get('any_sample_clear_at_probe') is not True:
            return None, 'declared probe absent or inconsistent with horizon'
        bounds.append(value)
    return min(bounds), 'minimum sampled clear-side bound across all approaches'


def attach_visibility(regions, polygons, footprint, visibility, native_lanes=None):
    """Attach the current subject's operational proxy to occupied lane/roadway regions."""
    from shapely.geometry import MultiPoint
    # Always clear old values; each frame must earn its own source-bound estimate.
    result = [{k:v for k,v in region.items() if k != 'sight_distance'} for region in regions]
    value, reason = sight_distance(visibility)
    mapping = {'value_m': None, 'attached_regions': [], 'reason': reason,
               'method': 'incoming_virtual_observer_to_subject_body',
               'value_kind': 'conservative_sampled_clear_distance'}
    if value is None:
        return result, mapping
    if native_lanes is not None:
        road = visibility.get('ego_projection', {}).get('road_id')
        expected = {lane for source_road, section, lane in native_lanes if source_road == road}
        if not expected or set(visibility['required_lane_ids']) != expected:
            mapping['reason'] = 'approach inventory differs from source driving lanes'
            return result, mapping
    points = visibility['ego_body_samples_m']
    measured_body = MultiPoint([(p[0], -p[1]) for p in points]).convex_hull
    if (footprint is None or footprint.is_empty or measured_body.area <= 0 or
            measured_body.hausdorff_distance(footprint) > 1e-6):
        mapping['reason'] = 'visibility targets differ from current subject footprint'
        return result, mapping
    selected = [r for r in result if r.get('kind') in ('lane', 'roadway')
                and r['id'] in polygons and polygons[r['id']].intersects(footprint)
                and polygons[r['id']].intersection(footprint).area > 0]
    if not selected:
        mapping['reason'] = 'no measured occupied lane or roadway region'
        return result, mapping
    for region in selected:
        region['sight_distance'] = value
    approaches = visibility['approaches']
    upper = [a['any_body_sight_horizon']['bracket_m'][1] for a in approaches
             if a['any_body_sight_horizon']['bound'] == 'first_sampled_occlusion']
    mapping.update(value_m=value, attached_regions=[r['id'] for r in selected],
                   eye_height_m=visibility['eye_height_m'],
                   visibility_criterion=visibility['visibility_criterion'],
                   distance_convention=visibility['distance_convention'],
                   probe_distance_m=visibility['probe_distance_m'],
                   scan_step_m=visibility['scan_step_m'],
                   horizon_tolerance_m=visibility['horizon_tolerance_m'],
                   lower_bound_m=value, upper_bound_m=min(upper) if upper else None,
                   search_censored=any(a['any_body_sight_horizon']['bound']=='at_least' for a in approaches),
                   approaches=approaches)
    return result, mapping
