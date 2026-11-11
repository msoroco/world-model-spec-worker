"""Build an explicitly diagnostic full-decode audit fixture, never a delivery receipt."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.media import compose_four_views
from delivery_audit import CAMERAS, audit_attempt, sha


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build(case_id, root):
    if root.exists():
        raise ValueError('Use a fresh diagnostic proof root')
    manifest=json.loads((FOLDER/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==case_id)
    diagnostic=json.loads((REPO/json.loads((REPO/entry['fixture_recipe']).read_text())['generator']['source']).read_text())
    construction=json.loads((FOLDER/entry['construction']).read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    config['duration_s']=.45
    attempt=root/'attempt';attempt.mkdir(parents=True)
    write(attempt/'config.json',config)
    for name in ('trace.jsonl','vehicle_history.jsonl','video_frames.jsonl'):
        (attempt/name).write_text(diagnostic['files'][name])
    mapping=[json.loads(x) for x in diagnostic['files']['video_frames.jsonl'].splitlines() if x]
    history=[json.loads(x) for x in diagnostic['files']['vehicle_history.jsonl'].splitlines() if x]
    write(attempt/'converted/trace.json',{'scenes':[{'t':round(row['time_s']*1000)} for row in mapping]})
    write(attempt/'result.json',{'case_id':case_id,'provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'physical_acceptance_claimed':False,
          'physical_checks':{'setup':{'status':'met'},'maneuver':{'status':'met'}},
          'realized_observables':{'diagnostic_only':True}})
    dimensions={'overview':(1920,1080),'approach':(1280,720),
                'reference_corner':(1280,720),'driver_reference':(1280,720)}
    for name,(width,height) in dimensions.items():
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                        '-i',f'testsrc=size={width}x{height}:rate=20','-frames:v',str(len(mapping)),
                        '-c:v','ffv1','-pix_fmt','yuv444p',str(attempt/(name+'.mkv'))],check=True)
    compose_four_views({name:attempt/(name+'.mkv') for name in CAMERAS},
                       attempt/'video_frames.jsonl',attempt/'raw.mkv')
    sealed={name:sha(attempt/name) for name in ('config.json','trace.jsonl','vehicle_history.jsonl',
                                                'video_frames.jsonl',*(n+'.mkv' for n in CAMERAS))}
    write(attempt/'capture-seal.json',{'format':'worker-sealed-capture','provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'frames':len(mapping),'sources':sealed,
          'events':['capture_finished','encoders_closed','restoration_verified'],
          'physical_acceptance_claimed':False})
    write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
    write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
          'native_exit_sha256':sha(attempt/'native-exit.json'),'diagnostic_fixture':True})
    actors=[('ego',history[0]['ego']['actor_id']),('lead',history[0]['lead']['actor_id'])]
    actors += [('other',row['actor_id']) for row in history[0].get('other_participants',[])]
    review={'case_id':case_id,'reviewer':'synthetic CPU fixture generator',
            'method':'testsrc pixel regions only; no actor identity or physical visibility assertion',
            'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
            'source_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS},
            'observations':[{'camera':name,'video_frame':0,'actor':actor,'actor_id':ident,
                             'bbox_xyxy':[0,0,dimensions[name][0],dimensions[name][1]]}
                            for name in CAMERAS for actor,ident in actors]}
    write(root/'pixel-review.json',review)
    return attempt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--output-root',required=True,type=Path)
    parser.add_argument('--negative-missing-source',action='store_true')
    parser.add_argument('--negative-review-identity',action='store_true')
    parser.add_argument('--negative-unsealed-source',action='store_true')
    args=parser.parse_args()
    root=args.output_root.resolve();attempt=build(args.case,root)
    if args.negative_missing_source:
        (attempt/'vehicle_history.jsonl').unlink()
    if args.negative_review_identity:
        review=json.loads((root/'pixel-review.json').read_text())
        observation=next(x for x in review['observations'] if x['actor']=='ego')
        observation['actor_id']=next(x['actor_id'] for x in review['observations'] if x['actor']=='lead')
        write(root/'pixel-review.json',review)
    if args.negative_unsealed_source:
        seal=json.loads((attempt/'capture-seal.json').read_text())
        del seal['sources']['vehicle_history.jsonl']
        write(attempt/'capture-seal.json',seal)
        write(attempt/'native-exit.json',{'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json')})
        write(attempt/'owner-release.json',{'event':'owner_released','operator_attested':True,
              'native_exit_sha256':sha(attempt/'native-exit.json'),'diagnostic_fixture':True})
    result=audit_attempt(attempt,args.case,'diagnostic-job',1,'diagnostic-recording',
                         root/'pixel-review.json',attempt/'diagnostic-audit.json',
                         root/'source-decode.json',diagnostic_selftest=True)
    if result['passed'] or not result['software_checks_passed'] or not result['diagnostic_fixture']:
        raise ValueError('Diagnostic proof claimed delivery acceptance')
    print(json.dumps({'case_id':args.case,'software_checks_passed':True,
                      'diagnostic_fixture':True,'physical_acceptance_claimed':False,
                      'audit_sha256':sha(attempt/'diagnostic-audit.json')}))


if __name__=='__main__':main()
