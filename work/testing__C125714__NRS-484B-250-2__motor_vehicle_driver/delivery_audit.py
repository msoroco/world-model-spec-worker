"""Independent C125714 saved-original audit for local delivery review.

This code reads sealed originals and processed output; it never runs CARLA or
sets a legal verdict. Diagnostic media cannot pass the delivery path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
CASES = frozenset(BASE+'__'+suffix for suffix in (
    'timing_below_training', 'timing_inside_training', 'timing_above_training',
    'yield_wait_for_other_clear', 'advance_at_release',
    'official_device_controlled', 'opposite_intends_left', 'opposite_makes_left'))
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
ORIGINALS = ('road.xodr', 'site-context.json', 'trace.jsonl',
             'video_frames.jsonl', 'ego-body-history.jsonl',
             'other-body-history.jsonl', 'controller-history.jsonl', *CAMERAS)
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def observed_left_turn(other):
    centers = []
    for row in other:
        vertices = row.get('body_vertices_xy_m', [])
        if not vertices:
            raise ValueError('original other vehicle body missing')
        centers.append((sum(p[0] for p in vertices)/len(vertices),
                        sum(p[1] for p in vertices)/len(vertices)))
    start, end = centers[0], centers[-1]
    pivot = min(centers, key=lambda p: math.hypot(p[0],p[1]))
    before = (pivot[0]-start[0],pivot[1]-start[1])
    after = (end[0]-pivot[0],end[1]-pivot[1])
    if min(math.hypot(*before),math.hypot(*after)) < 4:
        raise ValueError('original left-turn movement incomplete')
    return (before[0]*after[1]-before[1]*after[0]) / (
        math.hypot(*before)*math.hypot(*after)) > .7


def verify_frame_join(mapping, trace, ego, other, site, expected_frames, controller=None):
    """Check both actor identities, all original ticks, and 20 Hz timing."""
    if (not mapping or len(mapping) != expected_frames or
            len(trace) != len(mapping) or len(ego) != len(mapping) or
            len(other) != len(mapping) or
            (controller is not None and len(controller) != len(mapping))):
        raise ValueError('complete original participant/trace/frame count missing')
    if (type(site.get('ego_actor_id')) is not int or
            type(site.get('other_actor_id')) is not int or
            site['ego_actor_id'] == site['other_actor_id']):
        raise ValueError('two distinct original vehicle participants required')
    previous = None
    for index, (m, t, e, o) in enumerate(zip(mapping, trace, ego, other)):
        frame, time_s = m.get('carla_frame'), m.get('time_s')
        if (m.get('video_frame') != index or m.get('native_frame') != frame or
                type(frame) is not int or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or
                any((r.get('frame'), r.get('time_s')) != (frame,time_s)
                    for r in (t,e,o)) or
                e.get('actor_id') != site['ego_actor_id'] or
                o.get('actor_id') != site['other_actor_id']):
            raise ValueError('original participant/trace/video frame join changed')
        if previous and (frame != previous[0]+1 or
                         abs(time_s-previous[1]-.05) > 1e-4):
            raise ValueError('original frame clock is not contiguous at 20 Hz')
        previous = (frame,time_s)
    if controller is not None:
        for control, original in zip(controller, mapping):
            if (control.get('frame') != original['carla_frame'] or
                    control.get('time_s') != original['time_s'] or
                    type(control.get('ego_brake')) not in (int, float) or
                    not math.isfinite(control['ego_brake']) or
                    not 0 <= control['ego_brake'] <= 1):
                raise ValueError('original controller frame or brake join changed')
    return len(mapping)


def audit_sources(attempt, case_id):
    """Verify lifecycle and complete original source identity independently."""
    attempt = Path(attempt)
    if case_id not in CASES:
        raise ValueError('wrong C125714 exact delivery case')
    config = read(attempt/'config.json')
    if config.get('selected_case_id') != case_id:
        raise ValueError('original config selects another case')
    provenance = read(attempt/'acquisition-provenance.json')
    if (provenance.get('provenance_kind') != 'native' or
            provenance.get('diagnostic_fixture') is not False):
        raise ValueError('original Native acquisition required; diagnostic fixture rejected')
    seal = read(attempt/'capture-seal.json')
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('events') != ['capture_finished','encoders_closed','restoration_verified'] or
            seal.get('restoration',{}).get('restored') is not True or
            any(seal.get('encoder_exit_codes',{}).get(name[:-4]) != 0 for name in CAMERAS)):
        raise ValueError('sealed Native lifecycle or four encoders incomplete')
    exit_receipt = read(attempt/'native-exit.json')
    if (exit_receipt.get('event') != 'native_exit' or
            exit_receipt.get('capture_seal_sha256') != sha(attempt/'capture-seal.json') or
            exit_receipt.get('native_process_exit_code') != 0 or
            exit_receipt.get('capture_command_failed') is not False):
        raise ValueError('Native exit is not source-bound success')
    owner = read(attempt/'owner-release.json')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(attempt/'native-exit.json')):
        raise ValueError('server owner release missing or stale')
    acquisition = read(attempt/'acquisition.json')
    for name in ORIGINALS:
        path = attempt/name
        if (not path.is_file() or path.is_symlink() or
                acquisition.get(name,{}).get('kind') != 'original_native' or
                acquisition[name].get('sha256') != sha(path) or
                seal.get('sources',{}).get(name) != sha(path)):
            raise ValueError('sealed original missing or changed: '+name)
    site = read(attempt/'site-context.json')
    reviewed = attempt/'reviewed-context.json'
    if (not reviewed.is_file() or reviewed.is_symlink() or
            provenance.get('reviewed_context_sha256') != sha(reviewed) or
            site.get('map_sha256') != sha(attempt/'road.xodr') or
            site.get('subsection_4_context_reviewed') is not True):
        raise ValueError('reviewed crossing and statutory exception context not bound')
    from branch_alternatives import observe_context
    branch = observe_context(attempt/'site-context.json', attempt/'road.xodr', reviewed)
    suffix = case_id.removeprefix(BASE+'__')
    facts = branch['facts']
    if branch['case_id'] != case_id or facts['subsection_4_context'] is not True:
        raise ValueError('reviewed original crossing facts differ from exact delivery case')
    if suffix == 'official_device_controlled':
        signals = ET.fromstring((attempt/'road.xodr').read_bytes()).findall('.//signal')
        if (facts['different_highways_left_right'] is not True or
                facts['official_device_controlled'] is not True or
                not any(s.get('id') == site.get('official_device_id') for s in signals)):
            raise ValueError('official device governance lacks reviewed original map signal')
    elif suffix in ('opposite_intends_left','opposite_makes_left'):
        if (site.get('approach_relation') != 'opposite' or
                facts['official_device_controlled'] is not False or
                facts['opposite_intends_left'] is not True or
                facts['opposite_makes_left'] is not
                    (suffix == 'opposite_makes_left')):
            raise ValueError('opposite left-turn facts differ from exact delivery case')
        if suffix == 'opposite_makes_left' and not observed_left_turn(
                rows(attempt/'other-body-history.jsonl')):
            raise ValueError('original other vehicle did not make left turn')
    elif (facts['different_highways_left_right'] is not True or
            facts['official_device_controlled'] is not False or
            site.get('other_left_turn_intent') is not False):
        raise ValueError('reviewed original crossing facts differ from exact delivery case')
    expected = round(config['duration_s']*config['rate_hz'])
    count = verify_frame_join(*(rows(attempt/name) for name in
          ('video_frames.jsonl','trace.jsonl','ego-body-history.jsonl',
           'other-body-history.jsonl')), site, expected,
           controller=rows(attempt/'controller-history.jsonl'))
    result = read(attempt/'result.json')
    if (result.get('case_id') != case_id or
            any(result.get(key) is not True for key in
                ('setup_confirmed','behavior_attempted','maneuver_completed')) or
            any(result.get('physical_checks',{}).get(key,{}).get('status') != 'met'
                for key in ('setup','maneuver')) or
            result.get('legal_verdict_claimed') is True):
        raise ValueError('exact physical completion not established')
    return {'frames':count,'source_result_sha256':sha(attempt/'result.json'),
            'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'sources':{name:sha(attempt/name) for name in ORIGINALS},
            'first_time_s':rows(attempt/'video_frames.jsonl')[0]['time_s'],
            'last_time_s':rows(attempt/'video_frames.jsonl')[-1]['time_s']}


def audit(attempt, processing, decode_receipt, case_id, job_id,
          attempt_number, recording_id, promoted_video, promoted_trace,
          media_verify=None):
    """Bind saved processing, full source decode and primary pixels to originals."""
    attempt, processing = Path(attempt).resolve(), Path(processing).resolve()
    native = audit_sources(attempt,case_id)
    saved = read(processing)
    if (saved.get('format') != 'worker-saved-processing' or
            saved.get('passed') is not True or
            saved.get('recorded_only') is not True):
        raise ValueError('saved-only processing receipt absent or failed')
    verify_saved_join(saved, native, case_id)
    stage = Path(saved.get('analysis_directory',''))
    video, trace = Path(promoted_video).resolve(), Path(promoted_trace).resolve()
    if attempt.resolve() not in video.parents or attempt.resolve() not in trace.parents:
        raise ValueError('promoted primary video and Core trace must be in canonical attempt')
    if not video.is_file() or not trace.is_file():
        raise ValueError('promoted primary video or Core trace missing')
    final = saved.get('final_video_checks') or {}
    original_trace = stage/'traffic_spec/trace.json'
    if (final.get('video_sha256') != sha(video) or
            not original_trace.is_file() or sha(original_trace) != sha(trace) or
            saved.get('result_sha256') != sha(stage/'result.json')):
        raise ValueError('promoted media differs from saved-only processing')
    scenes = read(trace).get('scenes')
    mapping = rows(attempt/'video_frames.jsonl')
    if (not isinstance(scenes,list) or len(scenes) != native['frames'] or
            any(scene.get('t') != round(frame['time_s']*1000)
                for scene,frame in zip(scenes,mapping))):
        raise ValueError('Core trace differs from original frame map')
    from pixel_checks import pixel_presence
    checker = sha(Path(__file__).with_name('pixel_checks.py'))
    if media_verify is None:
        from worker_exchange.media import audit as audit_media, verify_receipt
        if not Path(decode_receipt).is_file():
            audit_media(video,native['frames'],
                checkers={'pixel_presence': (checker,pixel_presence)},
                mapping_sha256=native['frame_map_sha256'],receipt=decode_receipt)
        media_verify = verify_receipt
    media_verify(video,Path(decode_receipt),native['frames'],
                 mapping_sha256=native['frame_map_sha256'],
                 required_checks={'pixel_presence':checker})
    receipt = read(decode_receipt)
    checks = receipt.get('checks',{})
    if (checks.get('frame_count') != 'all-decoded-frames' or
            checks.get('pixel_presence') != checker or
            receipt.get('video_sha256') != sha(video)):
        raise ValueError('full decode or actual pixel review missing')
    auditor = Path(__file__).resolve()
    return {'format':'worker-delivery-audit','passed':True,
            'case_id':case_id,'job_id':job_id,'attempt':attempt_number,
            'recording_id':recording_id,'source_result_sha256':native['source_result_sha256'],
            'frames':native['frames'],'video':str(video.relative_to(attempt)),
            'video_sha256':sha(video),'trace':str(trace.relative_to(attempt)),
            'trace_sha256':sha(trace),'checks':{key:True for key in CHECKS},
            'auditor_path':str(auditor),'auditor_sha256':sha(auditor),
            'source_decode_receipt_path':str(Path(decode_receipt).resolve()),
            'source_decode_receipt_sha256':sha(decode_receipt),
            'source_decode_auditor_sha256':receipt.get('auditor_sha256'),
            'legal_verdict_claimed':False}


def verify_saved_join(saved, native, case_id):
    """Require the saved processor to name this exact case and same originals."""
    if (saved.get('case_id') != case_id or
            saved.get('originals_preserved') is not True or
            saved.get('missing_evidence') is not False or
            saved.get('timestamp_joins',{}).get('passed') is not True or
            saved['timestamp_joins'].get('frames') != native['frames'] or
            saved.get('physical_acceptance_claimed') is not False or
            saved.get('legal_acceptance_claimed') is not False):
        raise ValueError('saved exact-case/original-frame receipt differs')
    originals = saved.get('original_source_hashes')
    if (not isinstance(originals, dict) or
            any(originals.get(name) != digest for name,digest in
                native.get('sources',{}).items())):
        raise ValueError('saved original source hashes differ from Native seal')


def main():
    p = argparse.ArgumentParser()
    for arg in ('attempt','processing','decode-receipt','case','job-id',
                'attempt-number','recording-id','video','trace','output'):
        p.add_argument('--'+arg,required=True)
    a = p.parse_args()
    result = audit(a.attempt,a.processing,a.decode_receipt,a.case,a.job_id,
                   int(a.attempt_number),a.recording_id,a.video,a.trace)
    Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
