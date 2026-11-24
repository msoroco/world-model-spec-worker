"""Independent saved-result consistency audit for one exact crossing attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_delivery import audit as audit_sources
from native_capture import _source_path


def audit(attempt, survey_path):
    attempt = Path(attempt).resolve()
    result_path = attempt/'result.json'
    result = json.loads(result_path.read_text())
    sources = audit_sources(attempt,survey_path,decode_media=True)
    observed = sources['entry_measurement']
    if result.get('case_id') != sources['case_id'] or result.get('measured_values') != observed:
        raise ValueError('saved result differs from original crossing measurement')
    if result.get('realized_observables') != observed:
        raise ValueError('realized observables differ from original crossing measurement')
    targets = {row.get('target'):row for row in result.get('target_checks',[])}
    if set(targets) != {'ego_minus_other_entry_s','ego_response'}:
        raise ValueError('saved crossing target set incomplete')
    if (targets['ego_minus_other_entry_s'].get('measured') != observed['ego_minus_other_upper_entry_s'] or
            targets['ego_response'].get('measured') != observed['observed_ego_response']):
        raise ValueError('saved crossing targets differ from original measurement')
    video_refs = result.get('video_references')
    if not isinstance(video_refs,list) or len(video_refs) != 1:
        raise ValueError('one original primary video required')
    video = _source_path(attempt,video_refs[0])
    from scenario_pipeline.worker_exchange.media import audit as decode_video
    decoded = decode_video(video,900,mapping_sha256=sources['frame_map_sha256'])
    hashes = result.get('source_sha256',{})
    if (hashes.get('primary_video') != decoded['video_sha256'] or
            hashes.get('frame_map') != sources['frame_map_sha256'] or
            hashes.get('source_manifest') != hashlib.sha256((attempt/'source-manifest.json').read_bytes()).hexdigest()):
        raise ValueError('saved result original source binding differs')
    if any(key in result for key in ('legal_verdict','compliant','violating')):
        raise ValueError('saved result includes prohibited legal verdict')
    if result.get('legal_judgment') != 'unresolved' or result.get('physical_acceptance') != 'not_assessed':
        raise ValueError('saved result overclaims legal or physical acceptance')
    return {'case_id':sources['case_id'], 'saved_sources_verified':True,
            'all_camera_pixels_decoded':sources['all_camera_pixels_decoded'],
            'primary_video_decoded_frames':decoded['frames'],
            'primary_rgb_sha256':decoded['rgb_sequence_sha256'],
            'result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
            'physical_acceptance_claimed':False, 'legal_judgment':'unresolved'}
