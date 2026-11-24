"""Independent original body-route completion measurement for C108447.

The endpoint radius is the Native controller's engineering arrival tolerance.
It is not a statutory cutoff or proof of parcel authority.
"""
from __future__ import annotations

import math

from property_route import _traversed_property_ids


def evaluate(map_packet: dict, trace: dict, case_id: str) -> dict:
    body = trace.get('ego', [])
    entry_frame = trace.get('destination_entry_frame')
    method = 'original sampled body versus source-bound route endpoint'
    if not body or type(entry_frame) is not int:
        return {'status': 'unverified', 'method': method,
                'reason': 'body samples or destination entry frame missing', 'observed': {}}
    route = map_packet.get('roadway_route') if case_id.endswith('__ordinary_crossing') else None
    if route is None:
        parcels = map_packet.get('properties', [])
        selected_status = 'public' if case_id.endswith('__public_bypass') else 'private'
        traversed = set(_traversed_property_ids(body, parcels))
        selected = [p['id'] for p in parcels if p.get('status') == selected_status and p.get('id') in traversed]
        if len(selected) != 1:
            return {'status': 'not_met', 'method': method,
                    'reason': 'one source-classified property was not traversed',
                    'observed': {'traversed_property_ids': sorted(traversed)}}
        route = map_packet.get('connector_routes', {}).get(selected[0])
    if not isinstance(route, list) or len(route) < 3:
        return {'status': 'unverified', 'method': method,
                'reason': 'source route missing', 'observed': {}}
    entry = next((row for row in body if row.get('frame') == entry_frame), None)
    if entry is None or not all(math.isfinite(float(row.get(key, float('nan'))))
                                    for row in (body[0], entry) for key in ('x', 'y')):
        return {'status': 'unverified', 'method': method,
                'reason': 'finite original body entry sample missing', 'observed': {}}
    start = (float(body[0]['x']), float(body[0]['y']))
    end = (float(entry['x']), float(entry['y']))
    target = (float(route[-1][0]), float(route[-1][1]))
    displacement = math.dist(start, end)
    endpoint_error = math.dist(end, target)
    status = 'met' if entry_frame > body[0]['frame'] and displacement >= 1.0 and endpoint_error <= 1.5 else 'not_met'
    return {'status': status, 'method': method,
            'reason': None if status == 'met' else 'entry does not reach source route endpoint after motion',
            'observed': {'start_xy_m': list(start), 'entry_xy_m': list(end),
                         'source_endpoint_xy_m': list(target), 'entry_frame': entry_frame,
                         'displacement_m': displacement, 'endpoint_error_m': endpoint_error,
                         'engineering_endpoint_radius_m': 1.5}}
