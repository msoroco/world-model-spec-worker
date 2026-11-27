"""Reject an unaudited fire-station driveway or highway source packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_station_scene import case_by_id, validate_scene


REQUIRED = {'map', 'station', 'entrance', 'highway', 'person', 'authority'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(packet_path, case_id):
    packet_path = Path(packet_path).resolve()
    require(packet_path.is_file() and not packet_path.is_symlink(),
            'reviewed original site packet missing')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    case = case_by_id(case_id)
    require(case is not None and packet.get('case_id') == case_id,
            'reviewed fire-station packet exact case mismatch')
    require(packet.get('review_status') == 'reviewed_original_source' and
            packet.get('diagnostic_fixture') is False and
            packet.get('reviewer') and packet.get('review_method'),
            'independent original source review absent')
    sources = packet.get('sources')
    require(isinstance(sources, dict) and REQUIRED <= set(sources),
            'reviewed fire-station source inventory incomplete')
    for name, source in sources.items():
        require(isinstance(source, dict) and source.get('path') and
                source.get('sha256'), 'source identity missing: ' + name)
        path = (packet_path.parent / source['path']).resolve()
        require(path.is_relative_to(packet_path.parent) and path.is_file() and
                not path.is_symlink() and sha(path) == source['sha256'],
                'reviewed source bytes changed: ' + name)
    map_record = json.loads((packet_path.parent / sources['map']['path']).read_text(
        encoding='utf-8'))
    require(packet.get('map_id') == map_record.get('map_id') and
            len(map_record.get('opendrive_sha256', '')) == 64,
            'reviewed original map identity missing')
    scene = packet.get('scene')
    require(isinstance(scene, dict), 'reviewed fire-station scene missing')
    validate_scene(scene, case)
    require(scene.get('map_sha256') == sources['map']['sha256'] and
            scene.get('station_source_sha256') == sources['station']['sha256'] and
            scene.get('entrance_source_sha256') == sources['entrance']['sha256'] and
            scene.get('highway_source_sha256') == sources['highway']['sha256'] and
            scene.get('person_source_sha256') == sources['person']['sha256'] and
            scene.get('authority_source_sha256') == sources['authority']['sha256'],
            'scene is not bound to reviewed source bytes')
    require(packet.get('station_identity_review') ==
            'independent_original_review_required',
            'visual station markers cannot establish legal identity')
    return packet, case
