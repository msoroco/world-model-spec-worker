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
    summary = result.get('realized_observables',{}).get('entry_time_difference_s',{})
    if summary.get('value') != observed['ego_minus_other_upper_entry_s'] or summary.get('unit') != 's':
        raise ValueError('realized observables differ from original crossing measurement')
    from scenario_pipeline.batch_pipeline.validation import recording_evidence
    recording_evidence(result,result['recording_description'],lambda ref:_source_path(attempt,ref))
    original=json.loads((attempt/'original-trace.json').read_text())['frames']
    camera=json.loads((attempt/'original-camera-index.json').read_text())['channels']
    refs={row['name']:row['reference'] for row in result['recording_evidence']}
    expected={
        'ego_body_history':[row['ego'] for row in original],
        'other_body_history':[row['other'] for row in original],
        'governing_device_history':[row['governing_device_readback'] for row in original],
        'original_camera_index':[{name:camera[name][i] for name in ('front','rear','left','right')}
                                 for i in range(len(original))],
    }
    for name,values in expected.items():
        rows=[json.loads(line) for line in _source_path(attempt,refs[name]).read_text().splitlines()]
        if len(rows)!=len(original) or any(row.get('time_s')!=source['time_s'] or
                                           row.get('value')!=value
                                           for row,source,value in zip(rows,original,values)):
            raise ValueError('derived recording channel differs from original: '+name)
    targets = {row.get('target'):row for row in result.get('target_checks',[])}
    if set(targets) != {'ego_minus_other_entry_s','ego_response'}:
        raise ValueError('saved crossing target set incomplete')
    if (targets['ego_minus_other_entry_s'].get('measured') != observed['ego_minus_other_upper_entry_s'] or
            targets['ego_response'].get('measured') != observed['observed_ego_response']):
        raise ValueError('saved crossing targets differ from original measurement')
    video_refs = result.get('video_references')
    exported=attempt/'runtime-export/source-export.json'
    if exported.is_file():
        receipt=json.loads(exported.read_text())
        if (receipt.get('original_source_manifest_sha256') !=
                hashlib.sha256((attempt/'source-manifest.json').read_bytes()).hexdigest()):
            raise ValueError('runtime export differs from original source manifest')
        expected=['runtime-export/'+role+'.mkv' for role in
                  ('overview','approach','reference_corner','driver_reference')]
        if video_refs != expected or result.get('trace_reference')!='runtime-export/trace.jsonl':
            raise ValueError('four original runtime video references required')
        trace=_source_path(attempt,result['trace_reference'])
        if hashlib.sha256(trace.read_bytes()).hexdigest()!=receipt.get('trace_sha256'):
            raise ValueError('runtime export trace hash differs')
        for ref in expected:
            video=_source_path(attempt,ref)
            role=Path(ref).stem
            if (hashlib.sha256(video.read_bytes()).hexdigest()!=receipt['videos'][role]['sha256']):
                raise ValueError('runtime export video hash differs')
    elif video_refs != ['raw.mkv']:
        raise ValueError('one original primary video required')
    video = _source_path(attempt,'raw.mkv')
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
