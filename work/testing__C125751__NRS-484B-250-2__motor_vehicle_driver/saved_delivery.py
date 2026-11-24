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


def audit(root, survey_path):
    root = Path(root).resolve()
    manifest_path = root/'source-manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    case_id = manifest.get('case_id')
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in CASES}:
        raise ValueError('foreign saved crossing case')
    if manifest.get('source_kind') != 'original_native_acquisition':
        raise ValueError('original acquisition source kind missing')
    observation = measure_sealed(root, manifest_path, survey_path)
    if observation['case_id'] != case_id:
        raise ValueError('measurement case differs')
    trace = _sealed_json(root, manifest.get('trace'), 'original trace')
    index = _sealed_json(root, manifest.get('camera_index'), 'original camera index')
    if index.get('case_id') != case_id:
        raise ValueError('camera case differs')
    channels = index.get('channels')
    if not isinstance(channels, dict) or set(channels) != set(CAMERAS):
        raise ValueError('four original camera channels required')
    frames = trace['frames']
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
    return {'case_id':case_id, 'source_integrity':'passed',
            'native_frames':len(frames), 'camera_frames':len(frames)*len(CAMERAS),
            'camera_channels':list(CAMERAS), 'entry_measurement':observation,
            'physical_acceptance_claimed':False,
            'semantic_and_legal_judgment':'unresolved'}
