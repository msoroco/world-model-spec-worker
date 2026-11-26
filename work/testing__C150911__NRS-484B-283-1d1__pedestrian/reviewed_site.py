"""Verify a separately reviewed original C150911 WALK/crosswalk source packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'testing__C150911__NRS-484B-283-1d1__pedestrian'
REQUIRED = {'opendrive', 'crosswalk', 'pedestrian_signal', 'pedestrian_route',
            'vehicle_route', 'exceptions', 'cameras'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_review(packet: str | Path, source_root: str | Path, case_id: str) -> dict:
    packet = Path(packet).resolve()
    source_root = Path(source_root).resolve()
    review = json.loads(packet.read_text())
    if (review.get('assignment_id') != ASSIGNMENT or review.get('case_id') != case_id
            or review.get('cell_id') != 'C150911'):
        raise ValueError('reviewed WALK source identity differs')
    provenance = review.get('source_provenance', {})
    if (provenance.get('kind') != 'original_reviewed_site'
            or provenance.get('diagnostic_fixture') is not False
            or not provenance.get('reviewer') or not provenance.get('citation')):
        raise ValueError('external original reviewed WALK site provenance required')
    sources = review.get('sources')
    if not isinstance(sources, dict) or not REQUIRED <= set(sources):
        raise ValueError('reviewed WALK source inventory incomplete')
    loaded = {}
    for name in sorted(REQUIRED):
        item = sources[name]
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            raise ValueError('reviewed WALK source binding missing: ' + name)
        path = (source_root / item['path']).resolve()
        if not path.is_relative_to(source_root) or not path.is_file():
            raise ValueError('reviewed WALK source path invalid: ' + name)
        if sha(path) != item['sha256']:
            raise ValueError('reviewed WALK source hash differs: ' + name)
        loaded[name] = path.read_text() if name == 'opendrive' else json.loads(path.read_text())
    signal = loaded['pedestrian_signal']
    if (signal.get('official') is not True or not signal.get('governs_route_id')
            or type(signal.get('actor_id')) is not int
            or signal.get('allowed_indications') != ['walk', 'wait', 'dont_walk']):
        raise ValueError('official pedestrian signal identity and states required')
    crosswalk = loaded['crosswalk']
    if (not crosswalk.get('crosswalk_id') or not crosswalk.get('polygon_xy_m')
            or not crosswalk.get('one_way_road_id')):
        raise ValueError('reviewed crosswalk and one-way road missing')
    route = loaded['pedestrian_route']
    if (route.get('signal_route_id') != signal['governs_route_id']
            or route.get('crosswalk_id') != crosswalk['crosswalk_id']
            or not route.get('approach_xy_m') or not route.get('exit_xy_m')):
        raise ValueError('pedestrian crossing route and signal authority differ')
    vehicle = loaded['vehicle_route']
    if not vehicle.get('vehicle_actor_id') or not vehicle.get('conflict_zone_xy_m'):
        raise ValueError('distinct vehicle and conflict zone review required')
    exceptions = loaded['exceptions']
    if (not isinstance(exceptions, dict) or
            set(exceptions.get('reviewed_statutes', [])) !=
            {'NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350'}):
        raise ValueError('three introductory exception contexts require review')
    cameras = loaded['cameras']
    if set(cameras) != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('four reviewed camera poses required')
    return {'review': review, 'packet_sha256': sha(packet),
            'sources': loaded, 'source_root': str(source_root)}
