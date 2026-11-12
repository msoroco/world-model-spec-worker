"""Full diagnostic software path through truck delivery audit; no physical claim."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from delivery_audit import CAMERAS, SIZES, digest, require_native_delivery


FILES = ('config.json','road_context.json','truck_history.jsonl',
         'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl',
         'result.json','converted/trace.json','fixture-provenance.json')


def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')


def build(source, root, case):
    if root.exists():
        raise ValueError('Use a fresh diagnostic audit root')
    attempt = root/'attempt'
    attempt.mkdir(parents=True)
    for name in FILES:
        path=attempt/name
        path.parent.mkdir(parents=True,exist_ok=True)
        original = source.parents[0]/'converted/trace.json' if name == 'converted/trace.json' else source/name
        shutil.copyfile(original,path)
    for name, (width,height) in SIZES.items():
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                        '-f','lavfi','-i',f'color=c=black:s={width}x{height}:r=20',
                        '-vf','drawbox=x=16:y=16:w=32:h=32:color=red:t=fill',
                        '-frames:v','9','-c:v','ffv1','-pix_fmt','yuv444p',
                        str(attempt/(name+'.mkv'))],check=True)
    media = __import__('delivery_audit').media_module()
    media.compose_four_views({name:attempt/(name+'.mkv') for name in CAMERAS},
                             attempt/'video_frames.jsonl',attempt/'raw.mkv')
    sealed={name:digest(attempt/name) for name in
            ('config.json','road_context.json','truck_history.jsonl',
             'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl',
             *(name+'.mkv' for name in CAMERAS))}
    write(attempt/'capture-seal.json',{
        'format':'worker-sealed-capture','provenance_kind':'synthetic_fixture',
        'diagnostic_fixture':True,'frames':9,'sources':sealed,
        'physical_acceptance_claimed':False})
    write(attempt/'native-exit.json',{'capture_seal_sha256':digest(attempt/'capture-seal.json')})
    write(attempt/'owner-release.json',{'operator_attested':True,
        'native_exit_sha256':digest(attempt/'native-exit.json')})
    evidence=json.loads((attempt/'capture/evidence.jsonl').read_text().splitlines()[0])
    actors=evidence['original_observations']['participants']
    observations=[]
    for name in CAMERAS:
        for role, actor in zip(('ego','lead'),actors):
            observations.append({'camera':name,'video_frame':0,'actor':role,
                                 'actor_id':actor['actor_id'],'bbox_xyxy':[0,0,64,64]})
    write(root/'pixel-review.json',{'case_id':case,
        'reviewer':'diagnostic CPU generator',
        'method':'colored software fixture; no physical visibility claim',
        'frame_map_sha256':digest(attempt/'video_frames.jsonl'),
        'source_sha256':{name:digest(attempt/(name+'.mkv')) for name in CAMERAS},
        'observations':observations})
    return attempt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    args=parser.parse_args()
    root=args.output_root.resolve()
    attempt=build(args.source.resolve(),root,args.case)
    audit=require_native_delivery(attempt,args.case,'diagnostic-job',1,
                                  'diagnostic-recording',root/'pixel-review.json',
                                  attempt/'diagnostic-audit.json',root/'source-decode.json',
                                  diagnostic_selftest=True)
    if audit['passed'] or not audit['software_checks_passed'] or audit['diagnostic_fixture'] is not True:
        raise ValueError('Diagnostic audit claimed physical acceptance')
    original=attempt/'truck_history.jsonl'
    missing=attempt/'truck_history.jsonl.withheld'
    original.rename(missing)
    try:
        try:
            require_native_delivery(attempt,args.case,'diagnostic-job',1,
                                    'diagnostic-recording',root/'pixel-review.json',
                                    attempt/'negative-audit.json',root/'source-decode.json',
                                    diagnostic_selftest=True)
        except ValueError as error:
            if 'Missing original source: truck_history.jsonl' not in str(error):
                raise
            negative=str(error)
        else:
            raise ValueError('Missing original truck history was accepted')
    finally:
        missing.rename(original)
    print(json.dumps({'format':'worker-truck-delivery-diagnostic-proof',
                      'passed':True,'diagnostic_audit_passed':False,
                      'software_checks_passed':True,'physical_acceptance_claimed':False,
                      'audit_sha256':digest(attempt/'diagnostic-audit.json'),
                      'missing_original_negative':negative},sort_keys=True))


if __name__ == '__main__':
    main()
