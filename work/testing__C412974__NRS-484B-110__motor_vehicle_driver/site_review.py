"""Gate Native execution on reviewed original site and designation bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zone_motion import CASES, validate_scene


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_site(path: Path, case_id: str):
    path = Path(path).resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError('reviewed original site packet missing')
    packet = json.loads(path.read_text(encoding='utf-8'))
    case = next((c for c in CASES if case_id.endswith('__' + c.name)), None)
    if case is None or packet.get('case_id') != case_id:
        raise ValueError('reviewed packet exact case mismatch')
    if (packet.get('review_status') != 'reviewed_original_source' or
            packet.get('diagnostic_fixture') is not False or
            not packet.get('reviewer') or not packet.get('review_method')):
        raise ValueError('reviewed original safety-zone provenance missing')
    sources = packet.get('sources', {})
    required = {'map', 'highway', 'zone_boundary', 'designation', 'marking',
                'route', 'vehicle', 'driver'}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError('reviewed safety-zone source inventory incomplete')
    for name, source in sources.items():
        if not isinstance(source, dict) or not source.get('path') or not source.get('sha256'):
            raise ValueError('reviewed source identity missing: ' + name)
        target = (path.parent / source['path']).resolve()
        if (not target.is_relative_to(path.parent) or not target.is_file() or
                target.is_symlink() or sha(target) != source['sha256']):
            raise ValueError('reviewed source changed: ' + name)
    map_record = json.loads((path.parent / sources['map']['path']).read_text(encoding='utf-8'))
    if (packet.get('map_id') != map_record.get('map_id') or
            len(map_record.get('opendrive_sha256', '')) != 64):
        raise ValueError('reviewed map identity missing')
    scene = packet.get('scene', {})
    validate_scene(scene, case)
    for name in required:
        if scene[name + '_source_sha256'] != sources[name]['sha256']:
            raise ValueError('scene does not bind reviewed source bytes: ' + name)
    if not packet.get('vehicle_blueprint_id', '').startswith('vehicle.'):
        raise ValueError('motor-vehicle blueprint missing')
    markers = packet.get('zone_markers')
    if not isinstance(markers, list) or len(markers) < 4:
        raise ValueError('physical zone boundary markers absent')
    for marker in markers:
        if (not marker.get('blueprint_id', '').startswith('static.') or
                not isinstance(marker.get('xy'), list) or len(marker['xy']) != 2):
            raise ValueError('zone boundary marker invalid')
    if packet.get('designation_review') != 'independent_original_review_required':
        raise ValueError('physical marker does not establish official designation')
    return packet, case
