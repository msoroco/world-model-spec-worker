"""Independent local source/lifecycle audit for one delivered stripe case.

Run after saved processing with an actual Native attempt and pinned media decode
receipt. A passing result is software/physical-evidence validation, not law.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):return json.loads(Path(path).read_text())

def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def body(value):
    return isinstance(value,list) and len(value)>=4 and all(
        isinstance(vertex,list) and len(vertex)>=3 and all(
            type(component) in (int,float) and math.isfinite(component)
            for component in vertex[:3]) for vertex in value)


def envelope_gap(a,b):
    dx=max(min(v[0] for v in b)-max(v[0] for v in a),
           min(v[0] for v in a)-max(v[0] for v in b),0)
    dy=max(min(v[1] for v in b)-max(v[1] for v in a),
           min(v[1] for v in a)-max(v[1] for v in b),0)
    return math.hypot(dx,dy)


def audit(attempt, processing, decode_receipt, media_verify=None, case_id=None):
    attempt=Path(attempt);processing=Path(processing)
    seal=read(attempt/'capture-seal.json')
    if seal.get('events')!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    required_sources={'trace.jsonl','video_frames.jsonl','turn-history.jsonl',
                      'zone-context.json','zone-review-source.json','zone-authority-source.txt',
                      'acquisition.json','result.json'}
    if not required_sources<=set(seal.get('sources',{})):
        raise ValueError('Native seal omits required original source')
    for name,checksum in seal.get('sources',{}).items():
        if not (attempt/name).is_file() or sha(attempt/name)!=checksum:
            raise ValueError('sealed original missing or changed: '+name)
    exit_record=read(attempt/'native-exit.json')
    if exit_record.get('event')!='native_exit' or exit_record.get('capture_seal_sha256')!=sha(attempt/'capture-seal.json'):
        raise ValueError('Native exit does not bind sealed capture')
    owner=read(attempt/'owner-release.json')
    if owner.get('event')!='owner_released' or owner.get('operator_attested') is not True or owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json'):
        raise ValueError('owner release missing or stale')
    result=read(attempt/'result.json')
    if case_id is not None and result.get('case_id')!=case_id:
        raise ValueError('delivery case identity differs')
    if not all(result.get(key) is True for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('physical completion not confirmed')
    trace=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if not trace or len(trace)!=len(mapping) or any(
        t['frame']!=m['carla_frame'] or abs(t['time_s']-m['time_s'])>1e-6 or m['video_frame']!=i
        for i,(t,m) in enumerate(zip(trace,mapping))):
        raise ValueError('original frame/time join missing or changed')
    acquisition=read(attempt/'acquisition.json')
    for name in ('turn-history.jsonl','zone-context.json','zone-review-source.json',
                 'zone-authority-source.txt'):
        source=acquisition.get(name,{})
        if source.get('kind')!='original_native' or not (attempt/name).is_file() or source.get('sha256')!=sha(attempt/name):
            raise ValueError('original turn source missing or changed: '+name)
    turns=rows(attempt/'turn-history.jsonl')
    if len(turns)!=len(mapping) or any(
        h.get('frame')!=m['carla_frame'] or abs(h.get('time_s',-1)-m['time_s'])>1e-6 or
        not all(body(h.get(key)) for key in ('ego_body_vertices_m','oncoming_body_vertices_m','following_body_vertices_m')) or
        type(h.get('left_signal')) is not bool or
        any(not isinstance(h.get(role+'_velocity_xy_mps'),list) or
            len(h[role+'_velocity_xy_mps'])!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v)
                for v in h[role+'_velocity_xy_mps']) for role in ('oncoming','following')) or
        any(type(h.get(key)) not in (int,float) or not math.isfinite(h[key]) or h[key]<0
            for key in ('oncoming_body_gap_m','following_body_gap_m'))
        for h,m in zip(turns,mapping)):
        raise ValueError('original participant/body history incomplete or frame join changed')
    if any(abs(envelope_gap(h['ego_body_vertices_m'],h[role+'_body_vertices_m'])-
               h[role+'_body_gap_m'])>.1 for h in turns for role in ('oncoming','following')):
        raise ValueError('reported traffic gap differs from original body geometry')
    zone=read(attempt/'zone-context.json')
    if zone.get('striping_source')!='native_map' or zone.get('zone_kind')!='marked_no_passing_zone':
        raise ValueError('Native zone marking source is missing')
    from zone_source import validate as validate_zone_source
    source_facts=validate_zone_source(read(attempt/'zone-review-source.json'),
                                      (attempt/'zone-authority-source.txt').read_bytes(),zone)
    for key in ('zone_extent_verified','statutory_exceptions_verified',
                'destination_kind','authority_source_sha256','review_packet_sha256'):
        if zone.get(key)!=source_facts.get(key):
            raise ValueError('reviewed zone source differs from Native context: '+key)
    if zone.get('zone_extent_verified') is not True or zone.get('statutory_exceptions_verified') is not True:
        raise ValueError('statutory zone extent or exception context is unverified')
    processed=read(processing)
    if processed.get('format')!='worker-saved-processing' or processed.get('passed') is not True or processed.get('recorded_only') is not True:
        raise ValueError('saved processing receipt absent or failed')
    saved_result=Path(processed.get('result',''))
    if not saved_result.is_file() or processed.get('result_sha256')!=sha(saved_result):
        raise ValueError('saved result hash differs')
    saved=read(saved_result)
    if saved.get('case_id')!=result.get('case_id') or not all(saved.get(key) is True
            for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('saved result case or physical completion differs')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify=verify_receipt
    video=Path(processed.get('analysis_directory',''))/'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    media_verify(video,decode_receipt,len(mapping),mapping_sha256=sha(attempt/'video_frames.jsonl'))
    return {'format':'worker-delivery-audit','passed':True,'case_id':result.get('case_id'),
            'native_result_sha256':sha(attempt/'result.json'),'frame_count':len(mapping),
            'trace_sha256':sha(attempt/'trace.jsonl'),'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'video_sha256':sha(video),'source_decode_receipt_sha256':sha(decode_receipt),
            'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--processing',required=True);parser.add_argument('--decode-receipt',required=True)
    parser.add_argument('--case',required=True)
    args=parser.parse_args();print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt,case_id=args.case),indent=2))
if __name__=='__main__':main()
