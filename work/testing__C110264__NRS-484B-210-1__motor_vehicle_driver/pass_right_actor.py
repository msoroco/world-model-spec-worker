"""Read actual CARLA actor snapshots in a source-map station frame.

The map packet must carry world XY center points for each original cross
section. This module is CARLA-lazy and never treats requested motion as observed.
"""
from __future__ import annotations

import math


def _finite_pair(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in value)):
        raise ValueError('finite original world XY point required')
    return float(value[0]), float(value[1])


def _segments(packet):
    samples = packet.get('cross_sections', [])
    if len(samples) < 3 or packet.get('source_kind') != 'original_native_map_geometry':
        raise ValueError('original map cross sections required')
    out = []
    for a, b in zip(samples, samples[1:]):
        if a.get('source') != 'native_map' or b.get('source') != 'native_map':
            raise ValueError('original map cross section provenance required')
        s0, s1 = a.get('station_m'), b.get('station_m')
        if not all(isinstance(s, (int, float)) and math.isfinite(s) for s in (s0, s1)) or s1 <= s0:
            raise ValueError('ordered original stations required')
        x0, y0 = _finite_pair(a.get('world_center_xy_m'))
        x1, y1 = _finite_pair(b.get('world_center_xy_m'))
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.1 or abs(length - (s1 - s0)) > 0.1:
            raise ValueError('world polyline length differs from source stations')
        bounds0 = _finite_pair(a.get('paved_lateral_bounds_m'))
        bounds1 = _finite_pair(b.get('paved_lateral_bounds_m'))
        if bounds0[0] >= bounds0[1] or bounds1[0] >= bounds1[1]:
            raise ValueError('invalid original paved bounds')
        out.append((s0, s1, x0, y0, dx, dy, length, bounds0, bounds1))
    return out


def project_actor(packet, location, yaw_deg):
    """Project a snapshot pose to source station/right-positive lateral axes."""
    x, y = float(location.x), float(location.y)
    if not all(math.isfinite(v) for v in (x, y, yaw_deg)):
        raise ValueError('finite original actor pose required')
    candidates = []
    for s0, s1, x0, y0, dx, dy, length, bounds0, bounds1 in _segments(packet):
        u = ((x - x0) * dx + (y - y0) * dy) / (length * length)
        clamped = max(0.0, min(1.0, u))
        px, py = x0 + clamped * dx, y0 + clamped * dy
        distance = math.hypot(x - px, y - py)
        lateral = ((x - px) * dy - (y - py) * dx) / length
        bounds = tuple(bounds0[i] + clamped * (bounds1[i] - bounds0[i]) for i in (0, 1))
        forward_yaw = math.degrees(math.atan2(dy, dx))
        heading = ((forward_yaw - yaw_deg + 180.0) % 360.0) - 180.0
        candidates.append((distance, s0 + clamped * (s1 - s0), lateral, bounds, heading))
    candidates.sort(key=lambda row: row[0])
    best = candidates[0]
    if best[0] > max(abs(v) for v in best[3]) + 2.0:
        raise ValueError('actor too far from source map corridor')
    if len(candidates) > 1 and abs(candidates[1][0] - best[0]) < 0.05 and abs(candidates[1][1] - best[1]) > 2.0:
        raise ValueError('ambiguous original map projection')
    return {'s_m': best[1], 'lateral_m': best[2], 'paved_bounds_m': best[3],
            'heading_deg': best[4]}


def make_actor_sampler(packet, ego, target, *, left_signal_mask):
    """Return a same-tick snapshot reader for capture_native_attempt.

    The caller passes CARLA's VehicleLightState.LeftBlinker mask. Target light
    state is read back from the live actor after the captured snapshot tick.
    """
    if not isinstance(left_signal_mask, int) or left_signal_mask <= 0:
        raise ValueError('CARLA left signal bit mask required')
    half_width = packet.get('actor_half_width_m')
    if not isinstance(half_width, (int, float)) or not math.isfinite(half_width) or half_width <= 0:
        raise ValueError('source actor half width required')
    segments = _segments(packet)
    if not segments:
        raise ValueError('source segments required')
    if not isinstance(ego.id, int) or not isinstance(target.id, int) or ego.id == target.id:
        raise ValueError('distinct live actor IDs required')

    def sample(snapshot):
        result = {}
        for label, actor in (('ego', ego), ('target', target)):
            original = snapshot.find(actor.id)
            if original is None:
                raise ValueError(label + ' missing from original Native snapshot')
            transform, velocity = original.get_transform(), original.get_velocity()
            pose = project_actor(packet, transform.location, transform.rotation.yaw)
            speed = math.hypot(velocity.x, velocity.y)
            if not math.isfinite(speed):
                raise ValueError('nonfinite original actor speed')
            left, right = pose['paved_bounds_m']
            result[label + '_s_m'] = pose['s_m']
            result[label + '_lateral_m'] = pose['lateral_m']
            result[label + '_speed_mps'] = speed
            result[label + '_paved'] = left + half_width <= pose['lateral_m'] <= right - half_width
            if label == 'target':
                result['target_heading_deg'] = pose['heading_deg']
        state = int(target.get_light_state())
        result['target_left_signal'] = bool(state & left_signal_mask)
        return result

    return sample
