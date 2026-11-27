"""Independent exact-case original-source, full decode and pixel/physical audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from package_spec import AID,CAMERA_NAMES
from scooter_785 import CASES,need,validate_scene


def source(folder,name):
    path=folder/name
    need(path.is_file() and not path.is_symlink(),'Missing required source: '+name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_count(path):
    result=subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),
                           '-f','framemd5','-'],capture_output=True,text=True,timeout=300)
    need(result.returncode==0 and not result.stderr.strip(),
         'full original video decode failed: '+path.name)
    return sum(bool(line.strip()) and not line.startswith('#') for line in result.stdout.splitlines())


def audit(case_id,attempt,review,physical,diagnostic=False,site=None):
    attempt=Path(attempt).resolve()
    case=next((item for item in CASES if case_id==AID+'__'+item.name),None)
    need(case is not None,'unknown exact scooter case')
    receipt=json.loads(source(attempt,'original-source-receipt.json').read_text())
    need(receipt.get('case_id')==case_id and
         receipt.get('source_kind')==('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture') and
         receipt.get('diagnostic_fixture') is diagnostic,
         'original Native scooter source provenance differs')
    for key,name in (('history_sha256','scooter-history.json'),
                     ('trace_sha256','trace.jsonl'),
                     ('frame_map_sha256','video_frames.jsonl')):
        need(receipt.get(key)==sha(source(attempt,name)),
             'original source hash differs: '+name)
    history=json.loads(source(attempt,'scooter-history.json').read_text())
    scene=history['scene']
    validate_scene(scene,case)
    need(history.get('case_id')==case_id and
         (diagnostic or history.get('reviewed_site_sha256')==receipt.get('reviewed_site_sha256')),
         'reviewed scooter site/attempt binding differs')
    rows=history['samples']
    frames=[json.loads(line) for line in source(attempt,'video_frames.jsonl').read_text().splitlines()]
    traces=[json.loads(line) for line in source(attempt,'trace.jsonl').read_text().splitlines()]
    need(len(rows)==len(frames)==len(traces) and
         len(rows)==(9 if diagnostic else 900),
         'original frame/body/video count differs')
    for index,(row,frame,trace) in enumerate(zip(rows,frames,traces)):
        need(row['frame']==frame['video_frame']==index and
             row['original_frame']==frame['carla_frame']==trace['frame'] and
             row['time_s']==frame['time_s']==trace['time_s'] and
             row['speed_mps']==trace['speed_mps'],
             'original scooter frame/velocity join differs')
    if not diagnostic:
        need(site is not None,'independent original reviewed scooter site required')
        from runner import reviewed_site
        packet,_=reviewed_site(site,case_id)
        need(packet['reviewed_site_sha256']==receipt['reviewed_site_sha256'],
             'original reviewed site changed after capture')
    pixel=json.loads(Path(review).read_text())
    views=pixel.get('views')
    need(isinstance(views,dict) and set(views)==set(CAMERA_NAMES),
         'independent pixel review missing four views')
    for name in CAMERA_NAMES:
        video=source(attempt,name+'.mkv')
        declared=views[name]
        need(declared.get('video_sha256')==sha(video) and
             declared.get('frame_count')==len(frames) and
             (declared.get('synthetic_protocol_test') is True if diagnostic else
              declared.get('scooter_visible') is True and
              declared.get('lane_context_visible') is True),
             'independent pixel review lacks source-bound scooter/lane visibility: '+name)
        need(decode_count(video)==len(frames),'full original decode frame count differs: '+name)
        if not diagnostic:
            ref=receipt.get('cameras',{}).get(name,{})
            need(ref.get('sha256')==sha(video) and ref.get('frame_count')==len(frames),
                 'sealed original camera source differs: '+name)
    physical_result=json.loads(Path(physical).read_text())
    check=physical_result.get('physical_checks',{}).get('maneuver',{})
    need(physical_result.get('case_id')==case_id and
         check.get('status')=='met' and physical_result.get('maneuver_completed') is True,
         'independent physical completion missing')
    if not diagnostic:
        need(physical_result.get('provenance_kind')=='native' and
             check.get('sources',{}).get('trace.jsonl')==sha(attempt/'trace.jsonl'),
             'physical completion is not bound to original Native motion')
    return {'format':'scooter-785-independent-delivery-audit',
            'case_id':case_id,'passed':True,'diagnostic_fixture':diagnostic,
            'frame_count':len(frames),'video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERA_NAMES},
            'source_sha256':{name:sha(attempt/name) for name in
                             ('scooter-history.json','original-source-receipt.json',
                              'trace.jsonl','video_frames.jsonl')},
            'physical_status':check['status'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--physical',type=Path,required=True)
    parser.add_argument('--site',type=Path)
    parser.add_argument('--diagnostic-fixture',action='store_true')
    args=parser.parse_args()
    print(json.dumps(audit(args.case,args.attempt,args.review,args.physical,
                           args.diagnostic_fixture,args.site),indent=2))
