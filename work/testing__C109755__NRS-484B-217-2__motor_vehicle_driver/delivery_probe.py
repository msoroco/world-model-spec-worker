"""CPU fixture for exact-case independent audit, including a real decoded frame.

Generated files stay in .runtime-work; this does not claim Native provenance.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import audit


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def fixture(root,case):
    from worker_exchange.media import audit as media_audit
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    attempt=root/'attempt';stage=root/'stage';attempt.mkdir();stage.mkdir()
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
        '-f','lavfi','-i','color=c=blue:s=32x32:r=20','-frames:v','1',
        '-c:v','ffv1',str(stage/'raw.mkv')],check=True,timeout=30)
    frame=10;time_s=.5
    (attempt/'trace.jsonl').write_text(json.dumps({'frame':frame,'time_s':time_s})+'\n')
    (attempt/'video_frames.jsonl').write_text(json.dumps({'video_frame':0,'carla_frame':frame,'time_s':time_s})+'\n')
    body=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]
    row={'frame':frame,'time_s':time_s,'ego_body_vertices_m':body,
         'oncoming_body_vertices_m':[[v[0]+5,v[1],v[2]] for v in body],
         'following_body_vertices_m':[[v[0]-6,v[1],v[2]] for v in body],
         'left_signal':True,'oncoming_body_gap_m':4.0,'following_body_gap_m':5.0}
    (attempt/'turn-history.jsonl').write_text(json.dumps(row)+'\n')
    write(attempt/'zone-context.json',{'zone_kind':'marked_no_passing_zone','striping_source':'native_map',
         'zone_extent_verified':True,'statutory_exceptions_verified':True})
    write(attempt/'acquisition.json',{name:{'kind':'original_native','sha256':sha(attempt/name)}
        for name in ('turn-history.jsonl','zone-context.json')})
    result={'case_id':case,'setup_confirmed':True,'behavior_attempted':True,'maneuver_completed':True}
    write(attempt/'result.json',result);write(stage/'result.json',result)
    originals=('trace.jsonl','video_frames.jsonl','turn-history.jsonl','zone-context.json',
               'acquisition.json','result.json')
    write(attempt/'capture-seal.json',{'events':['capture_finished','encoders_closed','restoration_verified'],
         'sources':{name:sha(attempt/name) for name in originals}})
    write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
    write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
         'native_exit_sha256':sha(attempt/'native-exit.json')})
    write(root/'processing.json',{'format':'worker-saved-processing','passed':True,'recorded_only':True,
         'analysis_directory':str(stage),'result':str(stage/'result.json'),
         'result_sha256':sha(stage/'result.json')})
    media_audit(stage/'raw.mkv',1,mapping_sha256=sha(attempt/'video_frames.jsonl'),
                receipt=root/'source-decode.json')
    return attempt,root/'processing.json',root/'source-decode.json'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    attempt,processing,decode=fixture(args.output,args.case)
    if args.negative:
        row=json.loads((attempt/'turn-history.jsonl').read_text());del row['following_body_vertices_m']
        (attempt/'turn-history.jsonl').write_text(json.dumps(row)+'\n')
        acquisition=json.loads((attempt/'acquisition.json').read_text())
        acquisition['turn-history.jsonl']['sha256']=sha(attempt/'turn-history.jsonl')
        write(attempt/'acquisition.json',acquisition)
        seal=json.loads((attempt/'capture-seal.json').read_text())
        for name in ('turn-history.jsonl','acquisition.json'):
            seal['sources'][name]=sha(attempt/name)
        write(attempt/'capture-seal.json',seal)
        write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
        write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
             'native_exit_sha256':sha(attempt/'native-exit.json')})
    print(json.dumps(audit(attempt,processing,decode,case_id=args.case),indent=2))


if __name__=='__main__':main()
