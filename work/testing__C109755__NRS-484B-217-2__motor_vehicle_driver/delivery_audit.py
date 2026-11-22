"""Independent local source/lifecycle audit for one delivered stripe case.

Run after saved processing with an actual Native attempt and pinned media decode
receipt. A passing result is software/physical-evidence validation, not law.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):return json.loads(Path(path).read_text())

def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, processing, decode_receipt, media_verify=None):
    attempt=Path(attempt);processing=Path(processing)
    seal=read(attempt/'capture-seal.json')
    if seal.get('events')!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
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
    if not all(result.get(key) is True for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('physical completion not confirmed')
    trace=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if not trace or len(trace)!=len(mapping) or any(
        t['frame']!=m['carla_frame'] or abs(t['time_s']-m['time_s'])>1e-6 or m['video_frame']!=i
        for i,(t,m) in enumerate(zip(trace,mapping))):
        raise ValueError('original frame/time join missing or changed')
    processed=read(processing)
    if processed.get('format')!='worker-saved-processing' or processed.get('passed') is not True or processed.get('recorded_only') is not True:
        raise ValueError('saved processing receipt absent or failed')
    saved_result=Path(processed.get('result',''))
    if not saved_result.is_file() or processed.get('result_sha256')!=sha(saved_result):
        raise ValueError('saved result hash differs')
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
    args=parser.parse_args();print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt),indent=2))
if __name__=='__main__':main()
