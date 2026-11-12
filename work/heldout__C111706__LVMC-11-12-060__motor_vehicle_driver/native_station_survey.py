"""Native-only, source-bound fire-station site discovery for C111706.

No station identity is inferred from a CARLA object label alone: an operator
source and exact scene-object/map readback are both required.
"""
import hashlib
import json
from math import hypot
from pathlib import Path


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _scene_object(world, expected):
    objects = world.get_environment_objects()
    matches = [item for item in objects if item.id == expected['id']]
    if len(matches) != 1:
        raise ValueError('Station scene object absent or ambiguous')
    item = matches[0]
    if item.name != expected['name'] or str(item.type) != expected['type']:
        raise ValueError('Station scene object identity changed')
    actual = item.transform.location
    claimed = expected['location_m']
    if hypot(actual.x-claimed[0], actual.y-claimed[1]) > .25 or abs(actual.z-claimed[2]) > .25:
        raise ValueError('Station scene object transform changed')
    return {'id': item.id, 'name': item.name, 'type': str(item.type),
            'location_m': [float(actual.x), float(actual.y), float(actual.z)]}


def load_native_survey(path, world):
    path = Path(path).resolve()
    raw = path.read_bytes()
    manifest = json.loads(raw.decode('utf-8'))
    if manifest.get('format') != 'worker-fire-station-native-survey-v1':
        raise ValueError('Native station survey format mismatch')
    source = manifest.get('station_source', {})
    if source.get('kind') != 'operator_survey' or not source.get('reviewer') or not source.get('asset_id'):
        raise ValueError('Source-reviewed station identity required')
    if not source.get('source_path'):
        raise ValueError('Station source material path missing')
    material = (path.parent/source['source_path']).resolve()
    if not material.is_file() or _sha(material.read_bytes()) != source.get('source_sha256'):
        raise ValueError('Station source material missing or changed')
    material_bytes = material.read_bytes()
    material_bytes.decode('utf-8')
    world_map = world.get_map()
    opendrive_sha = _sha(world_map.to_opendrive().encode('utf-8'))
    if world_map.name != manifest.get('map_name') or opendrive_sha != manifest.get('opendrive_sha256'):
        raise ValueError('Native station map/OpenDRIVE source changed')
    scene = _scene_object(world, manifest['scene_object'])
    if source['asset_id'] != 'environment-object:' + str(scene['id']):
        raise ValueError('Station asset differs from scene object')
    survey = {key: manifest[key] for key in ('map_name', 'station_source', 'scene_object',
              'public_before', 'public_at', 'public_after', 'driveway_at', 'routes', 'other_route')}
    receipt = {'format': 'worker-fire-station-native-survey-receipt-v1',
               'manifest_sha256': _sha(raw), 'source_material_sha256': source['source_sha256'],
               'map_name': world_map.name, 'opendrive_sha256': opendrive_sha,
               'scene_object': scene, 'station_identity_review_pending': True,
               'physical_acceptance_claimed': False}
    return survey, receipt, raw, material_bytes
