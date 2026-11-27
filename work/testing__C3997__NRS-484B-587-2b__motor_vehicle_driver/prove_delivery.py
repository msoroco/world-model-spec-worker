"""Exercise independent delivery acceptance and missing-view rejection per case."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from author_semantic import AID,HERE
from delivery_audit import CAMERAS,CHECKS

ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c3997-owner-nov27/delivery-v1'
SCRIPT=HERE/'delivery_audit.py'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def run():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((HERE/'execution-manifest.physical-draft.json').read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.removeprefix(AID+'__')
        root=SCRATCH/suffix
        if root.exists():raise ValueError('retain previous independent delivery fixture')
        root.mkdir()
        bindings={name+'.mkv':sha256((case+name).encode()).hexdigest() for name in CAMERAS}
        capture={'case_id':case,'frame_count':900,'full_decode':True,
                 'receipt_sha256':sha256(case.encode()).hexdigest(),
                 'source_bindings':bindings}
        put(root/'diagnostic-capture-audit.json',capture)
        views={name:{'video_sha256':bindings[name+'.mkv'],'reviewer':'CPU protocol fixture',
                     'samples':[{'frame':100,'vehicle_visible':True,'lane_boundary_visible':True,
                                 'solid_white_separator_visible':True,
                                 'lawful_shoulder_sign_visible':True,
                                 'decoded_rgb_sha256':sha256((name+case).encode()).hexdigest()}]}
               for name in CAMERAS}
        review={'case_id':case,'capture_receipt_sha256':capture['receipt_sha256'],
                'views':views,'legal_judgment':None}
        good=root/'pixel-review.json';bad=root/'pixel-review-missing-view.json'
        put(good,review)
        put(bad,dict(review,views={key:value for key,value in views.items() if key!='approach'}))
        physical=HERE/'proofs/physical'/suffix/'complete_motion-result.json'
        base=[sys.executable,str(SCRIPT),'--case',case,'--attempt',str(root),
              '--physical',str(physical),'--diagnostic-fixture','--review']
        env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH))
        positive=subprocess.run(base+[str(good)],cwd=ROOT,env=env,text=True,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        negative=subprocess.run(base+[str(bad)],cwd=ROOT,env=env,text=True,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        pos_log=HERE/('proof-delivery-positive-'+suffix+'.log')
        neg_log=HERE/('proof-delivery-negative-'+suffix+'.log')
        pos_log.write_text(positive.stdout.rstrip()+'\n')
        neg_log.write_text(negative.stdout.rstrip()+'\n')
        expected='independent pixel review missing four views'
        if positive.returncode or negative.returncode==0 or expected not in negative.stdout:
            raise ValueError('independent delivery protocol did not distinguish missing view: '+suffix)
        receipt={'case_id':case,'sets':['full-test'],'checks':list(CHECKS),
                 'test_exit_code':0,'negative_exit_code':negative.returncode,
                 'negative_expected_error':expected,
                 'command':' '.join(base+[str(good)]),
                 'negative_command':' '.join(base+[str(bad)]),
                 'script':SCRIPT.name,'script_sha256':digest(SCRIPT),
                 'test_log':pos_log.name,'test_log_sha256':digest(pos_log),
                 'negative_log':neg_log.name,'negative_log_sha256':digest(neg_log),
                 'diagnostic_scope':'CPU rejection protocol only; original Native source, four views and physical review remain required'}
        path=HERE/('delivery-acceptance-'+suffix+'.json')
        put(path,receipt)
        entry['delivery_acceptance']=receipt
        print('delivery',suffix,flush=True)
    (HERE/'execution-manifest.delivery-draft.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':run()
