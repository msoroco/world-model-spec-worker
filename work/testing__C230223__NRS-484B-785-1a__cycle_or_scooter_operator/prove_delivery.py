"""Exercise independent delivery audit with positive/negative diagnostic protocols."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from package_spec import CAMERA_NAMES


HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'/'c230223_7851a_owner'
MANIFEST=HERE/'execution-manifest.draft.json'
PYTHON=ROOT/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def logged(command,log,env):
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,text=True)
    content='\n'.join(line.rstrip() for line in result.stdout.rstrip().splitlines())
    log.write_text(content+'\n' if content else '')
    return result


def main(tag):
    manifest=json.loads(MANIFEST.read_text())
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',
             SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH/'output'),
             TMPDIR=str(SCRATCH/'tmp'))
    for entry in manifest['cases']:
        cid=entry['case_id']
        slug=cid.removeprefix(HERE.name+'__')
        attempt=SCRATCH/'all-v1'/'compatibility'/slug/'primary'
        physical=HERE/'proofs'/'physical'/slug/'complete_motion-result.json'
        review_dir=SCRATCH/tag/slug
        review_dir.mkdir(parents=True,exist_ok=False)
        views={name:{'video_sha256':sha(attempt/(name+'.mkv')),
                     'frame_count':9,'synthetic_protocol_test':True}
               for name in CAMERA_NAMES}
        positive_review=review_dir/'pixel-review-protocol.json'
        negative_review=review_dir/'pixel-review-missing-view.json'
        write(positive_review,{'format':'synthetic-pixel-protocol',
                               'physical_visibility_claimed':False,'views':views})
        write(negative_review,{'format':'synthetic-pixel-protocol',
                               'physical_visibility_claimed':False,
                               'views':{name:row for name,row in views.items() if name!='driver_reference'}})
        base=[str(PYTHON),str(HERE/'delivery_audit.py'),'--case',cid,
              '--attempt',str(attempt),'--physical',str(physical),
              '--diagnostic-fixture']
        positive=base+['--review',str(positive_review)]
        negative=base+['--review',str(negative_review)]
        pos_log=HERE/('proof-delivery-'+slug+'-positive.log')
        neg_log=HERE/('proof-delivery-'+slug+'-negative.log')
        passed=logged(positive,pos_log,env)
        rejected=logged(negative,neg_log,env)
        error='independent pixel review missing four views'
        if (passed.returncode or json.loads(passed.stdout).get('passed') is not True or
                rejected.returncode==0 or error not in rejected.stdout):
            raise ValueError('independent delivery CPU audit failed: '+slug)
        entry['delivery_acceptance']={
            'case_id':cid,'sets':['full-test'],
            'checks':['native_source','all_participants','time_join',
                      'full_video_decode','actual_pixels','physical_completion'],
            'test_exit_code':0,'negative_exit_code':rejected.returncode,
            'negative_expected_error':error,
            'command':' '.join(positive),'negative_command':' '.join(negative),
            'script':'delivery_audit.py','script_sha256':sha(HERE/'delivery_audit.py'),
            'test_log':pos_log.name,'test_log_sha256':sha(pos_log),
            'negative_log':neg_log.name,'negative_log_sha256':sha(neg_log),
            'diagnostic_scope':'CPU source/decode protocol only; actual original pixels and physical acceptance remain local'}
        print('independent delivery positive/negative passed',slug,flush=True)
    write(MANIFEST,manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    main(args.tag)
