"""Independent original-source and saved-media audit for a wheelchair delivery."""
import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure

ORIGINAL_SOURCES=('encounter-history.jsonl','intersection-context.json','trace.jsonl',
                  'video_frames.jsonl','acquisition.json','road.xodr')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt,processing,decode_receipt,case_id,media_verify=None):
    attempt=Path(attempt);processing=Path(processing)
    seal=read(attempt/'capture-seal.json')
    if seal.get('events')!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(ORIGINAL_SOURCES)<=set(seal.get('sources',{})):
        raise ValueError('Native seal omits original wheelchair source')
    for name,digest in seal['sources'].items():
        if not (attempt/name).is_file() or sha(attempt/name)!=digest:
            raise ValueError('sealed original missing or changed: '+name)
    native_exit=read(attempt/'native-exit.json')
    if native_exit.get('event')!='native_exit' or native_exit.get('capture_seal_sha256')!=sha(attempt/'capture-seal.json'):
        raise ValueError('Native exit does not bind seal')
    owner=read(attempt/'owner-release.json')
    if owner.get('event')!='owner_released' or owner.get('operator_attested') is not True or owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json'):
        raise ValueError('owner release missing or stale')
    result=read(attempt/'result.json')
    if result.get('case_id')!=case_id or not all(result.get(key) is True for key in
       ('setup_confirmed','behavior_attempted','maneuver_completed')):
        raise ValueError('physical completion not confirmed for exact case')
    acquisition=read(attempt/'acquisition.json')
    for name in ORIGINAL_SOURCES[:2]:
        info=acquisition.get(name,{})
        if info.get('kind')!='original_native' or info.get('sha256')!=sha(attempt/name):
            raise ValueError('original wheelchair or context source absent: '+name)
    encounter=rows(attempt/ORIGINAL_SOURCES[0]);trace=rows(attempt/'trace.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if not encounter or not len(encounter)==len(trace)==len(mapping):
        raise ValueError('original frame streams incomplete')
    for index,(row,motion,frame) in enumerate(zip(encounter,trace,mapping)):
        identity=(frame.get('carla_frame'),frame.get('time_s'))
        if frame.get('video_frame')!=index or any((item.get('frame'),item.get('time_s'))!=identity
             for item in (row,motion)):
            raise ValueError('original wheelchair frame/time join changed')
    measured=measure(attempt)
    if measured['contact_frames']:
        raise ValueError('observed collision fails avoidance target')
    if case_id.endswith('__wheelchair_crossing') and measured['first_brake_frame'] is None:
        raise ValueError('crossing case lacks observed brake response')
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
    context=read(attempt/'intersection-context.json')
    config=read(attempt/'config.json')
    route=context.get('ego_route_geometry')
    if not isinstance(route,list) or len(route)!=3 or any(not isinstance(row,dict) for row in route) or [row.get('role') for row in route]!=['approach','crossing','exit'] or any(
       not all(key in row for key in ('x_m','y_m','road_id','lane_id')) for row in route):
        raise ValueError('original Native ego route geometry missing')
    expected_setup='crossing' if case_id.endswith('__wheelchair_crossing') else 'clear_path'
    if context.get('wheelchair_path_setup')!=expected_setup:
        raise ValueError('Native wheelchair path setup differs from exact case')
    return {'format':'worker-delivery-audit','passed':True,'case_id':case_id,
      'law_id':config['law_id'],'cell_id':config['cell_id'],'actor_id':config['actor'],
      'map_sha256':sha(attempt/'road.xodr'),
      'ego_route_sha256':hashlib.sha256(json.dumps(route,sort_keys=True).encode()).hexdigest(),
      'wheelchair_identity_sha256':hashlib.sha256((context['person_asset_source']+'|'+context['manual_wheelchair_asset_source']).encode()).hexdigest(),
      'camera_contract_sha256':hashlib.sha256(json.dumps(config.get('cameras',[]),sort_keys=True).encode()).hexdigest(),
      'duration_s':config['duration_s'],'measurement':measured,
      'native_result_sha256':sha(attempt/'result.json'),'frame_count':len(mapping),
      'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
      'video_sha256':sha(video),'source_decode_receipt_sha256':sha(decode_receipt),
      'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser()
    for name in ('attempt','processing','decode-receipt','case'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.attempt,args.processing,args.decode_receipt,args.case),indent=2))


if __name__=='__main__':main()
