"""Original body observations from supported capture producers; never replay."""
import hashlib
import json
import math
from pathlib import Path

SYNCHRONIZED_SOURCE = 'original_synchronized_motion_instance_v1'
_HELPER = '67ccf7e3c40a11d70c242beb632da409e7a50ba84647e42d120549d178cb9a6e'
_GENERATOR = '8aff8a733035eb9e80b4a2c875db0ff5b138366a37ef4b092a4c9d1abe6b0ff4'


def acquisition_contract(certificate, originals):
    manifest = json.loads(Path(originals['capture/manifest.json']).read_text())
    if manifest.get('acquisition') != 'original_live_run':
        raise ValueError('Unsupported original body acquisition contract')
    if manifest.get('observation_contract_version') in (2, 3):
        return 'original_observation_packets'
    if ('observation_contract_version' in manifest
            or certificate.get('body_capture_source') != SYNCHRONIZED_SOURCE):
        raise ValueError('Unsupported original body acquisition contract')
    required = ('synchronized_motion_records.jsonl', 'instance.json', 'worker_request.json',
                'runner.py', 'capture/recorder_info.txt')
    if any(name not in originals for name in required):
        raise ValueError('Missing original synchronized body source')
    request = json.loads(Path(originals['worker_request.json']).read_text())
    runtime = request.get('binding', {}).get('runtime_dependency_hashes', {})
    helpers = [value for name, value in runtime.items() if Path(name).name == 'pipeline_capture.py']
    instance = json.loads(Path(originals['instance.json']).read_text())
    if (helpers != [_HELPER] or manifest.get('generator_source', {}).get('sha256') != _GENERATOR
            or request.get('entrypoint') != 'runner.py'
            or request['binding'].get('case_id') != manifest.get('case_id')
            or instance.get('case', {}).get('case_id') != manifest.get('case_id')
            or instance.get('source_runner_sha256') != hashlib.sha256(Path(originals['runner.py']).read_bytes()).hexdigest()):
        raise ValueError('Original synchronized body producer binding differs')
    return SYNCHRONIZED_SOURCE


def source_events(certificate, originals):
    raw = [json.loads(line) for line in Path(originals['capture/evidence.jsonl']).read_text().splitlines() if line.strip()]
    events = {}
    for event in raw:
        frame = event['original_frame']
        if frame in events:
            raise ValueError('Duplicate original visibility frame')
        events[frame] = {'actor_id': event['actor_id'], 'recording_time_s': event['recording_time_s'],
                         'ego': {'body_vertices_m': event['ego']['body_vertices_m'], 'position_m': event['ego']['position_m']},
                         'participants': event.get('original_observations', {}).get('participants', []),
                         'devices': event.get('original_observations', {}).get('devices', [])}
    if not certificate.get('opaque_vehicle_enclosures'):
        return events
    if acquisition_contract(certificate, originals) != SYNCHRONIZED_SOURCE:
        return events
    from .adapter import original_participants
    from .visibility import _source_body_oriented_enclosure
    import numpy as np
    actors = original_participants(Path(originals['synchronized_motion_records.jsonl']), raw, 'original_live_run')
    instance = json.loads(Path(originals['instance.json']).read_text())
    physical = {row['actor_id']: row for row in instance['actor_physics'].values()}
    if len(physical) != len(instance['actor_physics']) or not physical:
        raise ValueError('Invalid original queried body inventory')
    for frame, event in events.items():
        participants = []
        if set(actors[frame]) != set(physical):
            raise ValueError('Original queried participant scope differs')
        for aid, actor in actors[frame].items():
            query = physical[aid]
            root = actor.get('actor_origin_m')
            if (query['blueprint'] != actor['blueprint'] or not isinstance(root, list) or len(root) != 3
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in root)
                    or query.get('bounding_box_rotation_deg') != [0., 0., 0.]):
                raise ValueError('Invalid original actor root/body query')
            body = np.asarray(actor['body_vertices_m'])
            basis = np.asarray(_source_body_oriented_enclosure(body.tolist())['axes'])
            extent = query['bounding_box_extent_m']; offset = query['bounding_box_offset_m']
            if (len(extent) != 3 or len(offset) != 3 or any(not math.isfinite(x) for x in extent + offset)
                    or any(x <= 0 for x in extent)):
                raise ValueError('Invalid original queried body dimensions')
            margin = 64*2**-23*max(1., float(np.abs(body).max()), *map(abs, root))
            local = (body - np.asarray(root)) @ basis.T
            center = actor.get('position_m')
            if (not isinstance(center, list) or len(center) != 3
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in center)):
                raise ValueError('Invalid original body-centre observation')
            if (float(np.abs(body.mean(axis=0) - center).max()) > margin
                    or float(np.abs(body.mean(axis=0) - (np.asarray(root) + basis.T @ offset)).max()) > margin
                    or float(np.abs((local.max(axis=0)-local.min(axis=0))/2 - extent).max()) > margin):
                raise ValueError('Original actor root/body geometry differs')
            if aid == event['actor_id'] and (actor['body_vertices_m'] != event['ego']['body_vertices_m']
                    or root != event['ego']['position_m']):
                raise ValueError('Original synchronized subject body/root differs')
            participants.append({'actor_id': aid, 'blueprint': actor['blueprint'],
                                 'position_m': root, 'body_vertices_m': actor['body_vertices_m']})
        event['participants'] = participants
    return events
