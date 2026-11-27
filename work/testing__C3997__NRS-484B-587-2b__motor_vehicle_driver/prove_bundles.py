"""Run pinned primary/fallback offline and positive/negative compatibility proofs."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from author_semantic import AID, HERE

ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c147331-owner-nov26/proofs-v2'
VALIDATOR=ROOT/'.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
MANIFEST=HERE/'execution-manifest.draft.json'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def command(args,log):
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run(args,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    log.write_text(result.stdout.rstrip()+'\n')
    if result.returncode:
        raise ValueError('exact CPU proof failed: '+log.name+'; '+result.stdout[-1000:])
    return result


def run():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    if not VALIDATOR.is_file():raise ValueError('pinned Lean validator missing')
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(AID+'__')
        for variant in ('primary','fallback1'):
            selected=entry if variant=='primary' else entry['candidates'][0]
            tag=suffix+'-'+variant
            offline=SCRATCH/('offline-'+tag)
            compatible=SCRATCH/('compatible-'+tag)
            if offline.exists() or compatible.exists():
                raise ValueError('retain prior proof output; choose a fresh version: '+tag)
            base=[sys.executable,str(ROOT/'runtime.py')]
            option=[] if variant=='primary' else ['--candidate',variant]
            offline_command=base+['offline','--manifest',str(MANIFEST),'--case',entry['case_id'],
                                  '--output',str(offline),'--python',sys.executable]+option
            offline_log=HERE/('proof-offline-'+tag+'.log')
            command(offline_command,offline_log)
            selected['offline']={'command':' '.join(offline_command),'exit_code':0,
                                 'log':offline_log.name,'log_sha256':digest(offline_log),
                                 'construction_sha256':selected['construction_sha256']}
            compat_command=base+['compatibility','--manifest',str(MANIFEST),
                                  '--case',entry['case_id'],'--output',str(compatible),
                                  '--library',str(ROOT/'runtime/library'),
                                  '--validator',str(VALIDATOR)]+option
            compat_command_log=HERE/('proof-compat-command-'+tag+'.log')
            command(compat_command,compat_command_log)
            receipt=HERE/('proof-compat-receipt-'+tag+'.json')
            analysis=HERE/('proof-compat-analysis-'+tag+'.log')
            negative=HERE/('proof-compat-negative-'+tag+'.log')
            shutil.copyfile(compatible/'compatibility.json',receipt)
            shutil.copyfile(compatible/'compatibility-analysis.log',analysis)
            shutil.copyfile(compatible/'negative-analysis.log',negative)
            proof=json.loads(receipt.read_text())
            if proof.get('passed') is not True or proof.get('construction_sha256')!=selected['construction_sha256']:
                raise ValueError('compatibility source binding differs: '+tag)
            selected['compatibility']={'receipt':receipt.name,'sha256':digest(receipt),
                                       'log':analysis.name,'negative_log':negative.name}
            if variant=='primary':
                entry['negative']={'log':negative.name}
                entry['acquisition']={name:{'entrypoint':'lane_native.py',
                                            'method':'PipelineCapture original tick plus source-sealed reviewed site and original-history.jsonl',
                                            'evidence':'original Native actor, map, source packet and four-view frame join'}
                                      for name in ['controlled_access_authority','public_highway_boundary',
                                                   'marked_lane_geometry','outside_lane_body_occupancy',
                                                   'shoulder_geometry_and_paving','lawful_shoulder_signage',
                                                   'vehicle_class_and_driver','emergency_necessity',
                                                   'subsection3_authorization']}
            print('proved',tag,flush=True)
    (HERE/'execution-manifest.proof-draft.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':run()
