"""Join original green-signal events and four lossless camera streams.

The operator supplies a source-surveyed scene, sensors, world lifecycle and
actor motion. This bridge never claims observed legal or physical acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path

from delivery_audit import PRODUCTION_PROFILE, audit_saved_delivery
from native_capture import capture
from native_scene import source
from original_camera_recorder import OriginalCameraRecorder
from saved_attempt import ASSIGNMENT


def capture_with_media(world, ego, other, site, site_ref, case_suffix,
                       signal_reader, attempt, sensors, scratch,
                       camera_profile_ref, context_ref, other_context_ref=None,
                       *, profile=PRODUCTION_PROFILE, diagnostic_fixture=False,
                       before_tick=None, after_tick=None):
    attempt = Path(attempt).resolve()
    scratch = Path(scratch).resolve()
    if not attempt.is_dir() or not scratch.is_dir() or '.runtime-work' not in scratch.parts:
        raise ValueError('materialized attempt and .runtime-work camera scratch required')
    if (attempt / 'media-capture-receipt.json').exists():
        raise ValueError('media receipt already exists')
    profile_path = source(camera_profile_ref, attempt)
    declared = json.loads(profile_path.read_text(encoding='utf-8'))
    if declared.get('fps') != 20 or declared.get('views') != {view: list(profile[view]) for view in profile}:
        raise ValueError('source-hashed camera profile differs')
    source(context_ref, attempt)
    recorder = OriginalCameraRecorder(sensors, scratch, profile=profile,
                                      diagnostic_fixture=diagnostic_fixture)
    try:
        captured = capture(world, ego, other, site, site_ref, case_suffix,
                           signal_reader, attempt, other_context_ref,
                           camera_profile_sha256=camera_profile_ref['sha256'],
                           camera_frame_reader=recorder.read,
                           before_tick=before_tick, after_tick=after_tick)
        media_refs = recorder.finish(attempt)
        original = captured['receipt']
        event_ref = original['event_ref']
        packet = {'assignment_id': ASSIGNMENT, 'case_id': original['case_id'],
                  'case_suffix': case_suffix, 'candidate': 'primary',
                  'attempt_id': 'native-' + event_ref['sha256'][:16],
                  'recording_id': 'original-' + event_ref['sha256'][:16],
                  'site_ref': site_ref, 'event_ref': event_ref,
                  'duration_frames': original['frame_count'],
                  'camera_profile_sha256': camera_profile_ref['sha256'],
                  'camera_profile_ref': camera_profile_ref,
                  'context_ref': context_ref,
                  'frame_map_ref': original['frame_map_ref'],
                  'camera_media_refs': media_refs}
        audit = audit_saved_delivery(packet, attempt, profile=profile,
                                     diagnostic_fixture=diagnostic_fixture)
        receipt = {'case_id': packet['case_id'], 'attempt_id': packet['attempt_id'],
                   'event_ref': event_ref, 'frame_map_ref': packet['frame_map_ref'],
                   'camera_media_refs': media_refs, 'camera_profile_ref': camera_profile_ref,
                   'context_ref': context_ref, 'camera_capture_complete': True,
                   'software_audit_passed': audit['software_audit_passed'],
                   'physical_acceptance_claimed': False,
                   'right_of_way_verdict': None}
        (attempt / 'media-capture-receipt.json').write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        return {'packet': packet, 'receipt': receipt, 'audit': audit,
                'measurement': captured['measurement']}
    finally:
        recorder.close()
