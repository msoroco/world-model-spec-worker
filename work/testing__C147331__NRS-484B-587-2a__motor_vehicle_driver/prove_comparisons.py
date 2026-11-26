"""Prove nine exact fixed-versus-deliberate source joins on synthetic histories."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from author_semantic import AID,HERE
from outside_lane import CASES

ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c147331-owner-nov26/comparison-v1'
SCRIPT=HERE/'comparison_audit.py'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def run():
    if SCRATCH.exists():raise ValueError('retain previous comparison source fixtures')
    SCRATCH.mkdir(parents=True)
    plan=json.loads((HERE/'case-plan.json').read_text())
    by_name={case.name:case for case in CASES}
    sources={}
    map_hash=sha256(b'synthetic C147331 comparison map').hexdigest()
    for case in CASES:
        fixed={'case':case.name,'ego_id':'synthetic-ego','map_sha256':map_hash,
               'lane_marking_source_sha256':'synthetic-markings',
               'legal_controlled_access_source_sha256':'synthetic-designation',
               'public_highway_boundary_source_sha256':'synthetic-boundary',
               'direction_source_sha256':'synthetic-direction',
               'camera_plan_sha256':'synthetic-camera',
               'sign_source_sha256':'synthetic-sign',
               'emergency_record_source_sha256':'synthetic-emergency',
               'subsection3_authorization_source_sha256':'synthetic-authorization',
               'vehicle_class':case.vehicle_class,'approach':case.approach,
               'route_class':case.route_class,
               'sign_permits_shoulder':case.sign_permits_shoulder,
               'emergency_required':case.emergency_required,
               'subsection3_authorized':case.subsection3_authorized,
               'source_sha256':'synthetic-frame-source',
               'capture_packet_sha256':'synthetic-packet'}
        path=SCRATCH/(case.name+'.jsonl')
        path.write_text(''.join(json.dumps(dict(fixed,original_frame=100+i))+'\n' for i in range(900)))
        sources[AID+'__'+case.name]=(path,digest(path))
    receipts=[]
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONDONTWRITEBYTECODE='1')
    for item in plan['comparisons']:
        comp=item['comparison_id']
        (left,lsha),(right,rsha)=[sources[x] for x in item['case_ids']]
        command=[sys.executable,str(SCRIPT),'--plan',str(HERE/'case-plan.json'),
                 '--comparison',comp,'--left-history',str(left),'--right-history',str(right),
                 '--left-sha256',lsha,'--right-sha256',rsha,'--map-sha256',map_hash]
        positive=subprocess.run(command,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        log=HERE/('proof-comparison-'+comp+'.log')
        log.write_text(positive.stdout.rstrip()+'\n')
        if positive.returncode or json.loads(log.read_text()).get('source_isolation_passed') is not True:
            raise ValueError('comparison proof failed: '+comp+' '+positive.stdout[-900:])
        bad=command.copy();bad[bad.index(lsha)]='0'*64
        negative=subprocess.run(bad,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        bad_log=HERE/('proof-comparison-negative-'+comp+'.log')
        bad_log.write_text(negative.stdout.rstrip()+'\n')
        if negative.returncode==0 or 'Native history hash mismatch' not in negative.stdout:
            raise ValueError('comparison stale-source rejection missing: '+comp)
        receipts.append({'comparison_id':comp,'case_ids':item['case_ids'],
                         'script':SCRIPT.name,'script_sha256':digest(SCRIPT),
                         'command':' '.join(command),'exit_code':0,
                         'log':log.name,'log_sha256':digest(log),
                         'negative_command':' '.join(bad),'negative_exit_code':negative.returncode,
                         'negative_log':bad_log.name,'negative_log_sha256':digest(bad_log),
                         'scope':'source-shaped CPU fixture; original comparison remains pending'})
        print('comparison',comp,flush=True)
    (HERE/'comparison-proposal.json').write_text(json.dumps({
        'format':'worker-comparison-proposal','assignment_id':AID,
        'comparisons':receipts},indent=2)+'\n')


if __name__=='__main__':run()
