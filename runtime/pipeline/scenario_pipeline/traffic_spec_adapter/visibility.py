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
            if low < 152.4 <= high and not (high == 152.4 and approach.get('any_sample_clear_at_probe') is False):
                return None, 'visibility bracket straddles 500 ft'
            value = low  # Clear-side bound, never the uncertain midpoint.
        elif h.get('bound') == 'at_least':
            value = h.get('distance_m')
            # A censored lower bound can answer the agreed 500 ft test only
            # when the search itself reached that distance. Otherwise unknown.
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid visibility search bound')
            if value < 152.4:
                return None, 'censored search shorter than 500 ft'
        else:
            return None, 'unknown horizon bound'
        if value >= 152.4 and approach.get('any_sample_clear_at_probe') is not True:
            return None, '500 ft probe absent or inconsistent with horizon'
        bounds.append(value)
    return min(bounds), 'minimum sampled clear-side bound across all approaches'


def attach_visibility(regions, polygons, footprint, visibility):
    """Copy structures per scene; attach only to road/lane regions ego overlaps.

    The value is relative to Scene.subject at this timestamp, not a static map
    property. Never put the subject's measurement on unrelated map regions.
    """
    distance, reason = sight_distance(visibility)
    structures = [dict(region) for region in regions]
    attached = []
    if distance is not None:
        for region in structures:
            polygon = polygons.get(region['id'])
            if region['kind'] in ('lane', 'roadway') and polygon is not None and footprint.intersects(polygon):
                region['sight_distance'] = distance
                attached.append(region['id'])
    if distance is not None and not attached:
        reason = 'ego does not overlap an observed road/lane region'
    return structures, {'value_m': distance if attached else None,
                        'attached_regions': attached, 'reason': reason}
