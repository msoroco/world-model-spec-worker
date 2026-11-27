"""Independent original bus-stop duration audit; rejects synthetic promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT='testing__C393262__LVMC-11-60-030-A5__bus_driver'
SUFFIXES=('park_below','park_at','park_above','stand_below','stand_at','stand_above')
VIEWS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(case_id: str, attempt: Path, source: dict, decode: dict, physical: dict,
           pixels: dict, activity: dict, designation: dict, core: dict) -> dict:
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in SUFFIXES}:
        raise ValueError('unknown exact bus duration case')
    attempt=attempt.resolve()
    if source.get('case_id')!=case_id or source.get('passed') is not True or source.get('source_kind')!='original_native_capture':
        raise ValueError('original Native source chain unverified')
    if physical.get('case_id')!=case_id or physical.get('provenance_kind')!='native' or physical.get('diagnostic_fixture') is not False:
        raise ValueError('original physical source absent')
    if physical.get('maneuver_completed') is not True:
        raise ValueError('complete bus arrival, interval and departure unverified')
    checks=physical.get('physical_checks',{})
    if not {'setup','target','maneuver'}<=set(checks):
        raise ValueError('physical checks incomplete')
    for item in checks.values():
        if item.get('status')!='met' or not item.get('sources'):
            raise ValueError('physical check lacks original sources')
        for relative,digest in item['sources'].items():
            path=(attempt/relative).resolve()
            if not path.is_relative_to(attempt) or not path.is_file() or sha(path)!=digest:
                raise ValueError('physical completion source changed: '+relative)
    frame_map=attempt/'video_frames.jsonl'
    rows=[json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes=core.get('scenes',[])
    if len(rows)!=900 or len(scenes)!=900 or source.get('frames')!=900:
        raise ValueError('900 original bus frames required')
    if source.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('original bus frame map changed')
    for index,(row,scene) in enumerate(zip(rows,scenes)):
        if row.get('video_frame')!=index or scene.get('t')!=round(row.get('time_s',-1)*1000):
            raise ValueError('Core/original bus frame time join differs')
    if decode.get('case_id')!=case_id or decode.get('passed') is not True:
        raise ValueError('full original video decode unverified')
    videos=decode.get('videos',{})
    if set(videos)!=set(VIEWS):
        raise ValueError('four original bus views required')
    for view in VIEWS:
        item=videos[view];path=attempt/(view+'.mkv')
        if item.get('frames')!=900 or item.get('sha256')!=sha(path):
            raise ValueError('decoded bus view source changed: '+view)
    if pixels.get('format')!='worker-original-pixel-review' or pixels.get('case_id')!=case_id or pixels.get('diagnostic_fixture') is not False or not pixels.get('reviewer'):
        raise ValueError('independent original bus pixel review missing')
    if pixels.get('frame_map_sha256')!=sha(frame_map) or pixels.get('video_sha256')!=sha(attempt/'overview.mkv'):
        raise ValueError('original bus pixel source changed')
    for name in ('bus_body','stop_boundary','residential_context','designation_signs'):
        item=pixels.get('observations',{}).get(name,{})
        if item.get('visible') is not True or item.get('view') not in VIEWS or not isinstance(item.get('frame'),int) or not 0<=item['frame']<900 or not item.get('description'):
            raise ValueError('actual bus-stop pixels unverified: '+name)
    if designation.get('case_id')!=case_id or designation.get('authority')!='City Traffic Engineer' or not designation.get('reviewer') or designation.get('diagnostic_fixture') is not False:
        raise ValueError('actual stop-specific designation review missing')
    d=designation.get('applicable_duration_s')
    if not isinstance(d,(int,float)) or d<=0 or not designation.get('conditions_reviewed'):
        raise ValueError('actual applicable designated duration missing')
    if designation.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('designation/original attempt join changed')
    if activity.get('case_id')!=case_id or activity.get('diagnostic_fixture') is not False or not activity.get('reviewer') or activity.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('independent original bus activity review missing')
    if activity.get('conduct')!=case_id.split('__')[-1].split('_')[0] or activity.get('complete_interval') is not True:
        raise ValueError('complete standing/parking interval unverified')
    measured=activity.get('measured_duration_s')
    if not isinstance(measured,(int,float)) or measured<=0 or activity.get('intervening_loading') is not False:
        raise ValueError('measured uninterrupted standing/parking interval missing')
    relation=case_id.split('__')[-1].split('_')[-1]
    delta=measured-d
    if (relation=='below' and not delta<-.05) or (relation=='at' and not abs(delta)<=.05) or (relation=='above' and not delta>.05):
        raise ValueError('original measured duration relation differs from selected probe')
    return {'format':'worker-bus-duration-delivery-audit','passed':True,'case_id':case_id,
            'checks':{key:True for key in CHECKS},'frames':900,
            'frame_map_sha256':sha(frame_map),'measured_duration_s':measured,
            'applicable_designated_duration_s':d,'legal_verdict':None}
