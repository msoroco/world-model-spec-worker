"""Source-gated geometry and observation checks for NRS 484B.307(8)(e).

This CPU checker reports observed predicates, never a legal verdict. Its inputs must
come from an original map/authority packet and a retained Native trace.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = a
        bx, by = b
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def _segment_intersection_parameters(p: tuple[float, float], q: tuple[float, float], a: list[float], b: list[float]) -> list[float]:
    dx, dy = q[0] - p[0], q[1] - p[1]
    ex, ey = b[0] - a[0], b[1] - a[1]
    denominator = dx * ey - dy * ex
    if abs(denominator) < 1e-10:
        return []
    rx, ry = a[0] - p[0], a[1] - p[1]
    t = (rx * ey - ry * ex) / denominator
    u = (rx * dy - ry * dx) / denominator
    return [t] if 0 <= t <= 1 and 0 <= u <= 1 else []


def _traversed_property_ids(samples: list[dict[str, Any]], properties: list[dict[str, Any]]) -> list[str]:
    traversed: set[str] = set()
    for left, right in zip(samples, samples[1:]):
        p = (float(left['x']), float(left['y']))
        q = (float(right['x']), float(right['y']))
        for parcel in properties:
            polygon = parcel['polygon_xy_m']
            cuts = [0.0, 1.0]
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                cuts.extend(_segment_intersection_parameters(p, q, a, b))
            cuts = sorted(set(cuts))
            for lo, hi in zip(cuts, cuts[1:]):
                if hi - lo <= 1e-8:
                    continue
                midpoint = (p[0] + (q[0] - p[0]) * (lo + hi) / 2, p[1] + (q[1] - p[1]) * (lo + hi) / 2)
                if _point_in_polygon(midpoint, polygon):
                    traversed.add(parcel['id'])
    return sorted(traversed)


def analyze(map_packet: dict[str, Any], trace: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Reject absent source links and return factual route/signal predicates."""
    source = map_packet.get('source', {})
    _require(source.get('kind') == 'original_native_map_and_property_authority', 'original map/property authority source required')
    _require(source.get('path') and source.get('sha256') and len(source['sha256']) == 64, 'map/property source path and seal required')
    _require(map_packet.get('coordinate_frame') == trace.get('coordinate_frame'), 'map/trace coordinate frame differs')
    properties = map_packet.get('properties', [])
    _require(properties and all(p.get('status') in ('public', 'private') and p.get('authority') for p in properties), 'property status and authority required')
    for parcel in properties:
        polygon = parcel.get('polygon_xy_m', [])
        _require(len(polygon) >= 3 and all(len(p) == 2 and all(math.isfinite(float(v)) for v in p) for p in polygon), 'invalid source property polygon')
    samples = trace.get('ego', [])
    _require(len(samples) >= 2 and all(a['frame'] < b['frame'] for a, b in zip(samples, samples[1:])), 'ordered ego body samples required')
    _require(all(math.isfinite(float(s[key])) for s in samples for key in ('x', 'y')), 'nonfinite ego position')
    _require(trace.get('actor_class') == 'vehicle' and trace.get('actor_source'), 'source-bound vehicle classification required')
    for name in ('approach_signal', 'destination_signal'):
        signal = trace.get(name, {})
        _require(signal.get('device_id') and signal.get('source') and signal.get('facing_ego') is not None, f'{name} identity, source and facing required')
        _require(signal.get('state') in ('red_alone', 'red_combined', 'yellow', 'green', 'dark', 'unknown'), f'{name} state required')
        _require(signal.get('frame') in [s['frame'] for s in samples], f'{name} frame must join ego samples')
    _require(trace.get('destination_street_id') == map_packet.get('intersecting_street_id'), 'destination street map join required')
    _require(trace.get('destination_entry_frame') in [s['frame'] for s in samples], 'destination entry frame required')
    _require(trace['destination_signal']['frame'] == trace['destination_entry_frame'], 'destination signal must be observed at entry')
    _require(trace.get('purpose', {}).get('source') and trace['purpose'].get('value') in ('avoid_red', 'other', 'unknown'), 'purpose must be a separate sourced or unknown observation')
    for name in ('approach_signal', 'destination_signal'):
        history = trace.get(name + '_history')
        if history is not None:
            _require(len(history) == len(samples), f'{name} history must cover every body frame')
            _require([row.get('frame') for row in history] == [row['frame'] for row in samples], f'{name} history frame join required')
            _require(all(row.get('device_id') == history[0].get('device_id') and row.get('source') and row.get('state') in ('red_alone', 'red_combined', 'yellow', 'green', 'dark', 'unknown') for row in history), f'{name} source and stable device required')
            _require(history[0] == trace[name] if name == 'approach_signal' else history[-1] == trace[name], f'{name} endpoint must match history')
    traversed = _traversed_property_ids(samples, properties)
    known = {p['id']: p for p in properties}
    approach_history = trace.get('approach_signal_history', [trace['approach_signal']])
    red_throughout = all(row['state'] == 'red_alone' and row['facing_ego'] is True for row in approach_history)
    bypass = bool(traversed) and red_throughout and trace['approach_signal']['facing_ego'] is True and trace['destination_signal']['state'] != 'red_alone' and trace['destination_signal']['state'] != 'red_combined' and trace['destination_signal']['state'] != 'unknown' and trace['destination_signal']['facing_ego'] is False and trace['purpose']['value'] == 'avoid_red'
    return {
        'case_id': case['case_id'],
        'traversed_property_ids': traversed,
        'traversed_property_statuses': [known[k]['status'] for k in traversed],
        'approach_red_alone_facing_ego': red_throughout,
        'destination_traffic_not_facing_red': trace['destination_signal']['state'] not in ('red_alone', 'red_combined', 'unknown') and trace['destination_signal']['facing_ego'] is False,
        'avoidance_purpose_observed_separately': trace['purpose']['value'] == 'avoid_red',
        'all_observation_conditions_present': bypass,
        'legal_judgment': None,
    }


def analyze_files(map_path: Path, trace_path: Path, case_path: Path) -> dict[str, Any]:
    map_packet = json.loads(map_path.read_text())
    declared = map_packet.get('source', {})
    original = Path(declared.get('path', ''))
    _require(original.is_file() and _sha(original) == declared.get('sha256'), 'original map/property source seal differs')
    return analyze(map_packet, json.loads(trace_path.read_text()), json.loads(case_path.read_text()))
