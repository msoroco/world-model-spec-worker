"""Saved signed U-turn analysis; proposed CPU entrypoint, no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from measure_u_turn import measure


def _rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _video_frames(path):
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Original source video decode failed: '+path.name)
    return int(result.stdout.strip())


def _original_joins(root):
    samples=_rows(root/'native_samples.jsonl')
    mapping=_rows(root/'video_frames.jsonl')
    trace=_rows(root/'trace.jsonl')
    evidence=_rows(root/'capture/evidence.jsonl')
    history=_rows(root/'body_history.jsonl')
    if not all(len(rows)==480 for rows in (samples,mapping,trace,evidence,history)):
        raise ValueError('Original Native/Core frame counts differ')
    for index,(n,m,t,e,b) in enumerate(zip(samples,mapping,trace,evidence,history)):
        frame=n['native_frame'];time=n['time_s']
        if (m['video_frame']!=index or m['carla_frame']!=frame or m['native_frame']!=frame
            or t['frame']!=frame or e['original_frame']!=frame or b['frame']!=frame):
            raise ValueError('Original Native/Core frame identity differs')
        if any(abs(row-time)>1e-4 for row in
               (m['time_s'],t['time_s'],e['recording_time_s'],b['time_s'])):
            raise ValueError('Original Native/Core timestamp differs')
        native={(round(p[0],5),round(p[1],5)) for p in n['native_body_xy_m']}
        captured={(round(p[0],5),round(p[1],5)) for p in e['ego']['body_vertices_m']}
        retained={(round(p[0],5),round(p[1],5)) for p in b['body_vertices_m']}
        if len(native)!=4 or native!=captured or captured!=retained:
            raise ValueError('Original Native/Core full body differs')
    manifest=json.loads((root/'capture/manifest.json').read_text())
    if not manifest.get('extraction_confirmed') or manifest.get('frames')!=480:
        raise ValueError('Original capture extraction incomplete')
    videos=[f'{name}.mkv' for name in ('overview','approach','sign_reference','driver_reference')]
    counts={name:_video_frames(root/name) for name in videos}
    if any(count!=480 for count in counts.values()):
        raise ValueError('Original camera frame count differs')
    return {'frames':480,'video_frames':counts,
            'source_hashes':{name:_sha(root/name) for name in
                ('trace.jsonl','capture/evidence.jsonl','body_history.jsonl',
                 'video_frames.jsonl','capture/manifest.json')}}


def _native_result(root, measured, joined):
    from worker_exchange.native_output import validate_result
    config=json.loads((root/'config.json').read_text())
    review=json.loads((root/'sign-review.json').read_text())
    samples=_rows(root/'native_samples.jsonl')
    expected=config['case_suffix']=='witness_2'
    observed=measured['u_turn_within_governed_region_observed']
    source_reviewed=review.get('reviewed_from_original_pixels') is True
    description=config['recording_description']
    evidence=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (root/reference).is_file():
            raise ValueError('Missing required source: '+reference)
        evidence.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    if not (root/'context.json').is_file():
        raise ValueError('Missing required source: context.json')
    for context in description['context_inputs']:
        evidence.append({'name':context['name'],'unit':context['unit'],'reference':'context.json'})
    result={'case_id':config['case_id'],
        'measured_values':{'signed_u_turn':measured},
        'target_checks':[{'target':'requested signed-region U-turn engineering target',
            'requested':expected,'measured':observed,
            'method':'original Native full-body, heading, lane and reviewed sign source',
            'tolerance':'source-measured boolean, no legal threshold inferred',
            'matched':observed is expected,
            'physical_cause_confirmed':source_reviewed,
            'cause_evidence':['native_samples.jsonl','sign-review.json','approach.mkv']}],
        'setup_confirmed':source_reviewed,
        'behavior_attempted':True,
        'maneuver_completed':(observed if expected else samples[-1]['native_center_xy_m'][0]>=10),
        'termination_reason':'full 480 original frames retained',
        'physical_failure_flags':([] if source_reviewed else ['original_pixel_sign_review_unverified'])+
            ([] if observed is expected else ['requested_movement_not_measured']),
        'trace_reference':'trace.jsonl',
        'video_references':list(joined['video_frames']),
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':evidence,
        'realized_observables':{},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    validate_result(result)
    return result


def measure_signed_u_turn(attempt):
    root=Path(attempt)
    return measure(root/'native_samples.jsonl',root/'video_frames.jsonl',
                   root/'sign-review.json',root/'approach.mkv')


def finalize(attempt,output):
    root=Path(attempt)
    if not (root/'native_samples.jsonl').is_file():
        raise ValueError('Missing required source: native_samples.jsonl')
    value=measure_signed_u_turn(root)
    full=(root/'trace.jsonl').is_file()
    joined=_original_joins(root) if full else None
    report={'format':'c104538-signed-u-turn-saved-analysis-v1',
            'measurements':{'signed_u_turn':{'method':'measure_signed_u_turn',
                'value':value,'sources':{
                    name:value['source_hashes'][Path(name).name] for name in
                    ('native_samples.jsonl','video_frames.jsonl','sign-review.json',
                     'pixel_review.jsonl','approach.mkv')}}},
            'original_joins':joined,'native_executed':False,'accepted':False,
            'legal_verdict_claimed':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    if full:
        result=_native_result(root,value,joined)
        with (root/'result.json').open('x') as stream:
            json.dump(result,stream,indent=2,allow_nan=False)
            stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)
