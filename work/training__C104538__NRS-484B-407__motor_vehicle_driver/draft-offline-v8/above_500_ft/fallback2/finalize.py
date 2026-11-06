"""Saved-only C104538 finalization; retains incomplete visibility and acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from measure_native import analyze,rows,sha

CAMERAS=('overview','reference_left','reference_right','ego')
CHANNELS=('drv.u_turn','st.curvature','st.grade','st.crest',
          'st.sight_distance','rel.oncoming','drv.approaching','kin.position')


def video_frames(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames',
        '-of','default=noprint_wrappers=1:nokey=1',str(path)],
        capture_output=True,text=True,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(result.stdout.strip())


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    measurement=analyze(attempt)
    count=measurement['original_frames']
    capture=json.loads((attempt/'capture/manifest.json').read_text())
    if (capture.get('case_id')!=config['case_id'] or
        capture.get('frames')!=count or capture.get('extraction_confirmed') is not True):
        raise ValueError('Original capture extraction incomplete')
    mapping=rows(attempt/'video_frames.jsonl')
    video_counts={name:video_frames(attempt/(name+'.mkv')) for name in CAMERAS}
    if any(value!=count for value in video_counts.values()):
        raise ValueError('Original source video frame count differs')
    for frame in mapping:
        pixel_hashes=frame.get('original_rgb_sha256')
        if not isinstance(pixel_hashes,dict) or set(pixel_hashes)!=set(CAMERAS) or any(
            not isinstance(value,str) or len(value)!=64 for value in pixel_hashes.values()):
            raise ValueError('Missing original camera RGB frame hash')
    recording_evidence=[]
    for name in CHANNELS:
        reference='channels/'+name+'.jsonl';source=rows(attempt/reference)
        if len(source)!=count or any(row.get('native_frame')!=mapping[index]['native_frame']
                                    for index,row in enumerate(source)):
            raise ValueError('Original observation channel join differs: '+name)
        recording_evidence.append({'name':name,'unit':'structured','reference':reference})
    target={'target':'two-direction original vehicle-body visibility within 500 ft',
            'requested':500,'measured':None,
            'method':'independent driver-eye/body/pixel audit required; saved geometry alone insufficient',
            'tolerance':0,'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':['driver_eye_rays.jsonl','video_frames.jsonl',
                              'reference_left.mkv','reference_right.mkv']}
    description=config.get('recording_description') or {
        'channels':[{'name':name,'unit':'structured','sampling_rate_hz':config['rate_hz']}
                    for name in CHANNELS],
        'limitations':['Original pixel visibility and legal outcome not independently audited']}
    result={'case_id':config['case_id'],'measured_values':measurement,
            'target_checks':[target],
            'setup_confirmed':False,
            'behavior_attempted':measurement['sampled_body_path_m']>0,
            'maneuver_completed':bool(measurement['engineering_reversal_observed'] and
                                      measurement['reverse_motion_observed']),
            'termination_reason':'full original Native duration retained',
            'physical_failure_flags':['original_pixel_visibility_unverified',
                                      'target_body_visibility_unverified'],
            'trace_reference':'trace.jsonl',
            'video_references':[name+'.mkv' for name in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':description,'recording_evidence':recording_evidence,
            'realized_observables':{
                'native_crest_height_error_m':{'value':measurement['maximum_native_crest_height_error_m'],
                    'unit':'m','method':'original Native waypoint elevation minus authored profile',
                    'time_window':'original map readback','statistic':'maximum absolute error',
                    'reference':'native-construction-context.json'},
                'barrier_box_gap_m':{'value':measurement['maximum_native_barrier_box_gap_m'],
                    'unit':'m','method':'adjacent original Native barrier actor world bounding boxes',
                    'time_window':'before original motion','statistic':'maximum gap',
                    'reference':'native-construction-context.json'}},
            'provenance_kind':'synthetic' if config.get('synthetic_fixture') is True else 'native',
            'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c104538-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],'measurements':{
                'turn_and_two_direction_visibility':{'value':{
                    'engineering_reversal_observed':measurement['engineering_reversal_observed'],
                    'two_direction_visibility_proven':False},
                    'method':'analyze','sources':measurement['source_sha256']},
                'crest_or_curve_at_turn':{'value':{
                    'maximum_native_crest_height_error_m':measurement['maximum_native_crest_height_error_m'],
                    'turn_location_on_authored_curve':False},
                    'method':'analyze','sources':measurement['source_sha256']},
                'multi_movement_reversal_history':{'value':{
                    'reverse_motion_observed':measurement['reverse_motion_observed'],
                    'engineering_reversal_observed':measurement['engineering_reversal_observed']},
                    'method':'analyze','sources':measurement['source_sha256']},
                'sightline_boundary_and_pixels':{'value':{
                    'original_pixel_visibility_proven':False,
                    'actual_body_visibility_proven':False},
                    'method':'pending_independent_original_pixel_audit',
                    'sources':measurement['source_sha256']}},
            'video_frames':video_counts,'capture_manifest_sha256':sha(attempt/'capture/manifest.json'),
            'scope':'saved original Native motion/map/actor evidence; no sightline pixel or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),allow_nan=False))
