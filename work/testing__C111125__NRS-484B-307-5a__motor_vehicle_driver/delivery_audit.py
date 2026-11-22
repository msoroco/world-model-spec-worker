"""Independent source and physical audit for one straight-arrow Native delivery."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt,processing,decode_receipt,case_id,media_verify=None):
    attempt=Path(attempt);processing=Path(processing)
    required=('signal-head-history.jsonl','ego-body-history.jsonl',
              'participant-history.jsonl','intersection-context.json',
              'trace.jsonl','video_frames.jsonl','acquisition.json','result.json')
    seal=read(attempt/'capture-seal.json')
    if seal.get('events')!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(required)<=set(seal.get('sources',{})):
        raise ValueError('Native seal omits original straight-arrow source')
    for name,digest in seal['sources'].items():
        if not (attempt/name).is_file() or sha(attempt/name)!=digest:
            raise ValueError('sealed original missing or changed: '+name)
    exit_record=read(attempt/'native-exit.json')
    if exit_record.get('event')!='native_exit' or exit_record.get('capture_seal_sha256')!=sha(attempt/'capture-seal.json'):
        raise ValueError('Native exit does not bind seal')
    owner=read(attempt/'owner-release.json')
    if owner.get('event')!='owner_released' or owner.get('operator_attested') is not True or owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json'):
        raise ValueError('owner release missing or stale')
    original=read(attempt/'result.json')
    if original.get('case_id')!=case_id:
        raise ValueError('delivery case identity differs')
    if not all(original.get(key) is True for key in ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('physical completion not confirmed')
    acquisition=read(attempt/'acquisition.json')
    for name in required[:4]:
        info=acquisition.get(name,{})
        if info.get('kind')!='original_native' or info.get('sha256')!=sha(attempt/name):
            raise ValueError('original signal, body or context source absent: '+name)
    signals=rows(attempt/required[0]);ego=rows(attempt/required[1]);traffic=rows(attempt/required[2])
    trace=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if not signals or not all(len(stream)==len(mapping) for stream in (signals,ego,traffic,trace)):
        raise ValueError('original frame streams incomplete')
    for index,(signal,body,participants,position,frame) in enumerate(zip(signals,ego,traffic,trace,mapping)):
        identity=(frame.get('carla_frame'),frame.get('time_s'))
        if frame.get('video_frame')!=index or any((stream.get('frame'),stream.get('time_s'))!=identity
            for stream in (signal,body,participants,position)):
            raise ValueError('original frame/time join changed')
    from analysis import measure
    measured=measure(attempt)
    if measured['first_sole_arrow_frame'] is None or measured['first_ego_intersection_entry_frame'] is None:
        raise ValueError('sole arrow or straight entry unobserved')
    if measured['entry_without_verified_arrow_frames']:
        raise ValueError('intersection entry without verified sole arrow')
    if abs(measured['observed_heading_change_deg'])>15:
        raise ValueError('observed heading is not straight')
    occupied=bool(measured['lawfully_occupied_frames'])
    if case_id.endswith('__clear_straight') and occupied:
        raise ValueError('clear case contains lawful occupancy')
    if case_id.endswith('__yield_straight') and not occupied:
        raise ValueError('yield case lacks lawful occupancy')
    if measured['ego_past_stop_line_during_occupancy_frames']:
        raise ValueError('ego passed stop line before yield cleared')
    processed=read(processing)
    if processed.get('format')!='worker-saved-processing' or processed.get('passed') is not True or processed.get('recorded_only') is not True:
        raise ValueError('saved processing receipt absent or failed')
    saved_result=Path(processed.get('result',''))
    if not saved_result.is_file() or processed.get('result_sha256')!=sha(saved_result) or read(saved_result).get('case_id')!=case_id:
        raise ValueError('saved result missing, stale or wrong case')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify=verify_receipt
    video=Path(processed.get('analysis_directory',''))/'raw.mkv'
    if not video.is_file():raise ValueError('saved primary video missing')
    media_verify(video,decode_receipt,len(mapping),mapping_sha256=sha(attempt/'video_frames.jsonl'))
    return {'format':'worker-delivery-audit','passed':True,'case_id':case_id,
            'native_result_sha256':sha(attempt/'result.json'),'frame_count':len(mapping),
            'trace_sha256':sha(attempt/'trace.jsonl'),'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'video_sha256':sha(video),'source_decode_receipt_sha256':sha(decode_receipt),
            'measurement':measured,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--processing',required=True);parser.add_argument('--decode-receipt',required=True)
    parser.add_argument('--case',required=True);args=parser.parse_args()
    print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt,args.case),indent=2))


if __name__=='__main__':main()
