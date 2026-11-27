"""Validate the reviewed original roadwork site before any Native construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from excavation_park import CASES, rect, validate_scene


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(packet_path: Path, case_id: str):
    packet_path = Path(packet_path).resolve()
    require(packet_path.is_file() and not packet_path.is_symlink(),
            'reviewed original site packet missing')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    case = next((item for item in CASES if case_id.endswith('__' + item.case_id)), None)
    require(case is not None and packet.get('case_id') == case_id,
            'reviewed packet exact case mismatch')
    require(packet.get('review_status') == 'reviewed_original_source' and
            packet.get('diagnostic_fixture') is False and
            packet.get('reviewer') and packet.get('review_method'),
            'reviewed original site provenance missing')
    sources = packet.get('sources')
    require(isinstance(sources, dict) and
            {'map', 'highway', 'excavation', 'traffic', 'authority'} <= set(sources),
            'reviewed source inventory incomplete')
    for name, source in sources.items():
        require(isinstance(source, dict) and source.get('path') and source.get('sha256'),
                'reviewed source identity missing: ' + name)
        target = (packet_path.parent / source['path']).resolve()
        require(target.is_relative_to(packet_path.parent) and target.is_file() and
                not target.is_symlink() and sha(target) == source['sha256'],
                'reviewed source changed: ' + name)
    map_record = json.loads((packet_path.parent / sources['map']['path']).read_text())
    require(packet.get('map_id') == map_record.get('map_id') and
            len(map_record.get('opendrive_sha256', '')) == 64,
            'reviewed map identity missing')
    scene = packet.get('scene')
    require(isinstance(scene, dict), 'reviewed scene missing')
    validate_scene(scene, case)
    require(scene['excavation_source_sha256'] == sources['excavation']['sha256'] and
            scene['highway_source_sha256'] == sources['highway']['sha256'] and
            scene['traffic_actor_source_sha256'] == sources['traffic']['sha256'] and
            scene['exception_source_sha256'] == sources['authority']['sha256'],
            'scene does not bind reviewed source bytes')
    require(packet.get('vehicle_blueprint_id', '').startswith('vehicle.') and
            packet.get('traffic_blueprint_id', '').startswith('vehicle.'),
            'motor-vehicle blueprints missing')
    require(rect(scene['excavation_rect_m']) and
            isinstance(packet.get('excavation_markers'), list) and
            len(packet['excavation_markers']) >= 2,
            'physical excavation markers absent')
    for marker in packet['excavation_markers']:
        require(marker.get('blueprint_id', '').startswith('static.') and
                isinstance(marker.get('xy'), list) and len(marker['xy']) == 2 and
                all(type(x) in (int, float) for x in marker['xy']),
                'roadwork marker construction incomplete')
    require(packet.get('excavation_source_review') == 'independent_original_review_required',
            'markers alone cannot establish a highway excavation')
    return packet, case
