"""Audit saved original crossing sources before any semantic proposal.

This is an integrity and frame-join receipt. It makes no claim about physical
visibility, legal priority, or whether a simulator is a production source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from entry_timing import ASSIGNMENT, CASES, measure_sealed
from native_capture import CAMERAS, _source_path


def _sealed_json(root, ref, label):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError(f'{label} reference missing')
    path = _source_path(root, ref['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError(f'{label} digest differs')
    return json.loads(raw)


def audit(root, survey_path, *, decode_media=True):
    root = Path(root).resolve()
    manifest_path = root/'source-manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    case_id = manifest.get('case_id')
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in CASES}:
        raise ValueError('foreign saved crossing case')
    if manifest.get('source_kind') != 'original_native_acquisition':
        raise ValueError('original acquisition source kind missing')
    original_survey = _source_path(root, manifest.get('survey',{}).get('path'))
    original_map = _source_path(root, manifest.get('opendrive',{}).get('path'))
    if (hashlib.sha256(original_survey.read_bytes()).hexdigest() != manifest.get('survey',{}).get('sha256') or
            original_survey.read_bytes() != Path(survey_path).read_bytes()):
        raise ValueError('saved original crossing survey differs')
    if (hashlib.sha256(original_map.read_bytes()).hexdigest() != manifest.get('opendrive',{}).get('sha256') or
            json.loads(original_survey.read_text()).get('opendrive_sha256') != manifest['opendrive']['sha256']):
        raise ValueError('saved original OpenDRIVE differs')
    observation = measure_sealed(root, manifest_path, survey_path)
    if observation['case_id'] != case_id:
        raise ValueError('measurement case differs')
    trace = _sealed_json(root, manifest.get('trace'), 'original trace')
    index = _sealed_json(root, manifest.get('camera_index'), 'original camera index')
    map_ref = manifest.get('frame_map')
    if not isinstance(map_ref, dict) or not isinstance(map_ref.get('path'), str):
        raise ValueError('original frame map reference missing')
    map_path = _source_path(root, map_ref['path'])
    map_raw = map_path.read_bytes()
    if hashlib.sha256(map_raw).hexdigest() != map_ref.get('sha256'):
        raise ValueError('original frame map digest differs')
    mapping = [json.loads(line) for line in map_raw.splitlines()]
    if index.get('case_id') != case_id:
        raise ValueError('camera case differs')
    channels = index.get('channels')
    if not isinstance(channels, dict) or set(channels) != set(CAMERAS):
        raise ValueError('four original camera channels required')
    frames = trace['frames']
    if len(mapping) != len(frames):
        raise ValueError('original frame map count differs')
    for index_number,(row,frame) in enumerate(zip(mapping,frames)):
        if (row.get('video_frame') != index_number or
                row.get('carla_frame') != frame['native_frame_id'] or
                row.get('native_frame') != frame['native_frame_id'] or
                row.get('time_s') != frame['native_elapsed_seconds']):
            raise ValueError('original frame map identity differs')
    dimensions = {}
    if decode_media:
        from PIL import Image
    for name in CAMERAS:
        refs = channels[name]
        if not isinstance(refs, list) or len(refs) != len(frames):
            raise ValueError('original camera frame count differs')
        for row,ref in zip(frames, refs):
            if (not isinstance(ref, dict) or ref.get('channel') != name or
                    ref.get('frame') != row['native_frame_id']):
                raise ValueError('original camera frame/channel join differs')
            path = _source_path(root, ref.get('source_path'))
            if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get('source_sha256'):
                raise ValueError('original camera media digest differs')
            if decode_media:
                try:
                    with Image.open(path) as image:
                        image.load()
                        if image.format != 'PNG' or image.mode not in ('RGB', 'RGBA'):
                            raise ValueError('original camera PNG format differs')
                        size = list(image.size)
                except (OSError, SyntaxError) as error:
                    raise ValueError('original camera pixels cannot decode') from error
                if name in dimensions and size != dimensions[name]:
                    raise ValueError('original camera dimensions changed')
                dimensions[name] = size
    return {'case_id':case_id, 'source_integrity':'passed',
            'native_frames':len(frames), 'camera_frames':len(frames)*len(CAMERAS),
            'camera_channels':list(CAMERAS), 'camera_dimensions':dimensions,
            'frame_map_sha256':map_ref['sha256'],
            'all_camera_pixels_decoded':decode_media,
            'entry_measurement':observation,
            'physical_acceptance_claimed':False,
            'semantic_and_legal_judgment':'unresolved'}
