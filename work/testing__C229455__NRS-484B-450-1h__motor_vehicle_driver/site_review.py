"""Gate Native execution on reviewed original safety-zone and curb source bytes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from safety_zone import CASES, validate_scene


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path, case_id):
    path = Path(path).resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError('reviewed original site packet missing')
    packet = json.loads(path.read_text(encoding='utf-8'))
    case = next((c for c in CASES if case_id.endswith('__' + c.case_id)), None)
    if case is None or packet.get('case_id') != case_id:
        raise ValueError('reviewed packet exact case mismatch')
    if (packet.get('review_status') != 'reviewed_original_source' or
            packet.get('diagnostic_fixture') is not False or
            not packet.get('reviewer') or not packet.get('review_method')):
        raise ValueError('reviewed original safety-zone provenance missing')
    sources = packet.get('sources', {})
    required = {'map', 'highway', 'zone', 'curb', 'designation', 'route', 'traffic', 'authority'}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError('reviewed safety-zone source inventory incomplete')
    for name, source in sources.items():
        if not isinstance(source, dict) or not source.get('path') or not source.get('sha256'):
            raise ValueError('reviewed source identity missing: ' + name)
        target = (path.parent / source['path']).resolve()
        if (not target.is_relative_to(path.parent) or not target.is_file() or
                target.is_symlink() or sha(target) != source['sha256']):
            raise ValueError('reviewed source changed: ' + name)
    map_record = json.loads((path.parent / sources['map']['path']).read_text())
    if (packet.get('map_id') != map_record.get('map_id') or
            len(map_record.get('opendrive_sha256', '')) != 64):
        raise ValueError('reviewed map identity missing')
    scene = packet.get('scene', {})
    validate_scene(scene, case)
    for field in ('map', 'highway', 'zone', 'curb', 'designation', 'route', 'traffic', 'exception'):
        if scene[field + '_source_sha256'] != sources[{'exception': 'authority'}.get(field, field)]['sha256']:
            raise ValueError('scene does not bind reviewed source bytes: ' + field)
    if (not packet.get('vehicle_blueprint_id', '').startswith('vehicle.') or
            not packet.get('traffic_blueprint_id', '').startswith('vehicle.')):
        raise ValueError('motor-vehicle blueprint missing')
    if not isinstance(packet.get('zone_markers'), list) or len(packet['zone_markers']) < 4:
        raise ValueError('visible zone boundary markers absent')
    for marker in packet['zone_markers']:
        if (not marker.get('blueprint_id', '').startswith('static.') or
                not isinstance(marker.get('xy'), list) or len(marker['xy']) != 2):
            raise ValueError('zone boundary marker invalid')
    if packet.get('designation_review') != 'independent_original_review_required':
        raise ValueError('physical marker does not establish official designation')
    return packet, case
