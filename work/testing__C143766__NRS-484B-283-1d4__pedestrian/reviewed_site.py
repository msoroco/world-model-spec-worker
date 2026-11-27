"""Require separately reviewed original trail, highway, signal and destination sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pedestrian_crossing import validate_site

ASSIGNMENT = 'testing__C143766__NRS-484B-283-1d4__pedestrian'
REQUIRED = {'opendrive', 'trail', 'highway', 'crossing', 'sidewalk',
            'pedestrian_signal', 'pedestrian_route', 'destinations',
            'exceptions', 'cameras'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_review(packet: str | Path, source_root: str | Path, case_id: str) -> dict:
    packet, source_root = Path(packet).resolve(), Path(source_root).resolve()
    review = json.loads(packet.read_text())
    if (review.get('assignment_id') != ASSIGNMENT or review.get('case_id') != case_id or
            review.get('cell_id') != 'C143766'):
        raise ValueError('reviewed crossing source identity differs')
    provenance = review.get('source_provenance', {})
    if (provenance.get('kind') != 'original_reviewed_site' or
            provenance.get('diagnostic_fixture') is not False or
            not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed crossing site provenance required')
    sources = review.get('sources')
    if not isinstance(sources, dict) or not REQUIRED <= set(sources):
        raise ValueError('reviewed crossing source inventory incomplete')
    loaded = {}
    for name in sorted(REQUIRED):
        item = sources[name]
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed crossing source binding missing: ' + name)
        path = (source_root / item['path']).resolve()
        if not path.is_relative_to(source_root) or not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('reviewed crossing source path/hash invalid: ' + name)
        loaded[name] = path.read_text() if name == 'opendrive' else json.loads(path.read_text())
    signal = loaded['pedestrian_signal']
    if (signal.get('official') is not True or type(signal.get('actor_id')) is not int or
            signal.get('facing_pedestrian') is not True or
            not {'walk', 'flashing', 'steady'} <= set(signal.get('allowed_phases', [])) or
            signal.get('countdown_capability') not in ('present', 'absent', 'switchable')):
        raise ValueError('official facing pedestrian signal and countdown review required')
    route = loaded['pedestrian_route']
    if not route.get('pedestrian_actor_id') or not route.get('route_id'):
        raise ValueError('reviewed pedestrian route identity missing')
    if route.get('signal_actor_id') != signal['actor_id']:
        raise ValueError('pedestrian route and signal authority differ')
    destinations = loaded['destinations']
    if not isinstance(destinations, dict) or not {'curb', 'sidewalk', 'safety_zone', 'other_place'} <= set(destinations):
        raise ValueError('all four separately sourced destination routes required')
    site = {'cell_id': 'C143766', 'actor': 'pedestrian',
        'trail_source_sha256': review['sources']['trail']['sha256'],
        'highway_source_sha256': review['sources']['highway']['sha256'],
        'crossing_source_sha256': review['sources']['crossing']['sha256'],
        'sidewalk_source_sha256': review['sources']['sidewalk']['sha256'],
        'signal_source_sha256': review['sources']['pedestrian_signal']['sha256'],
        'signal_facing_source_sha256': review['sources']['pedestrian_signal']['sha256'],
        'signal_facing_pedestrian': True,
        'trail_route_xy': loaded['trail'].get('route_xy'),
        'crossing_route_xy': loaded['crossing'].get('route_xy'),
        'highway_polygon_xy': loaded['highway'].get('polygon_xy'),
        'destination_routes': destinations,
        'safety_zone_provided_source_sha256': review['sources']['destinations']['sha256'],
        'other_place_safety_review_sha256': review['sources']['destinations']['sha256']}
    validate_site(site)
    if (not loaded['sidewalk'].get('accessible') or
            loaded['crossing'].get('route_id') != route['route_id'] or
            set(loaded['exceptions'].get('reviewed_statutes', [])) !=
            {'NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350'}):
        raise ValueError('accessible sidewalk, route or exception source review missing')
    cameras = loaded['cameras']
    if set(cameras) != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('four reviewed camera poses required')
    return {'review': review, 'packet_sha256': sha(packet), 'sources': loaded,
            'site': site, 'source_root': str(source_root)}
