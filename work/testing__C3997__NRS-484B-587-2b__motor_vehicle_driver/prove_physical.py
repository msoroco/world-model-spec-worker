"""Three source-shaped physical outcomes and Native ownership lifecycle per case."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from author_semantic import AID,HERE

ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c3997-owner-nov27/physical-v1'
PROOFS=HERE/'proofs/physical'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
    if path.stat().st_size>2*1024*1024:raise ValueError('physical proof file too large')


def prepare_import():
    allowed=(ROOT/'.runtime-work').resolve()
    output=Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT','')).resolve()
    if output!=allowed and allowed not in output.parents:
        raise ValueError('export private .runtime-work output root before runtime import')
    sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))


def outcome(config,suffix,kind,construction_sha):
    from worker_exchange.native_output import physical_result
    root=SCRATCH/suffix/kind
    if root.exists():raise ValueError('retain prior physical source-shaped fixture')
    root.mkdir(parents=True)
    put(root/'config.json',config)
    put(root/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})
    mapping=[{'video_frame':i,'carla_frame':100+i,'native_frame':100+i,'time_s':i/20}
             for i in range(900)]
    (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
    if kind!='missing_evidence':
        distance=200 if kind=='complete_motion' else 1
        trace=[{'frame':100+i,'time_s':i/20,
                'position_m':[distance*i/899,0,0],
                'heading_deg':0,'speed_mps':distance/45}
               for i in range(900)]
        (root/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
    target={'target':'source-specified original route progress','requested':'finite original motion',
            'measured':kind,'method':'source-shaped 900-frame diagnostic motion',
            'tolerance':0,'matched':kind=='complete_motion',
            'physical_cause_confirmed':False,'cause_evidence':{'config.json':digest(root/'config.json')}}
    result={'case_id':config['selected_case_id'],'measured_values':{},
            'target_checks':[target],'setup_confirmed':False,'behavior_attempted':False,
            'maneuver_completed':False,'termination_reason':'CPU physical fixture only',
            'physical_failure_flags':['synthetic_fixture'],
            'trace_reference':'trace.jsonl','video_references':['overview.mkv'],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':config['recording_description'],
            'recording_evidence':[],'realized_observables':{}}
    result=physical_result(root,result)
    path=PROOFS/suffix/(kind+'-result.json')
    put(path,result)
    expected={'complete_motion':'met','incomplete_motion':'not_met',
              'missing_evidence':'unverified'}[kind]
    status=result['physical_checks']['maneuver']['status']
    if status!=expected:raise ValueError('physical outcome status differs: '+kind+' '+status)
    log=PROOFS/suffix/(kind+'.log')
    log.write_text('case '+config['selected_case_id']+'\nkind '+kind+'\nstatus '+status+
                   '\nsource-shaped synthetic fixture; construction '+construction_sha+'\n')
    return {'kind':kind,'command':'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c3997-owner-nov27 .venv-cpu/bin/python work/'+AID+'/prove_physical.py --all',
            'exit_code':0,'log':str(log.relative_to(HERE)),'log_sha256':digest(log),
            'result':str(path.relative_to(HERE)),'result_sha256':digest(path)}


def lifecycle(config,suffix):
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release
    root=SCRATCH/suffix/'lifecycle'
    if root.exists():raise ValueError('retain prior lifecycle source-shaped fixture')
    root.mkdir(parents=True)
    put(root/'construction.json',{'case_id':config['selected_case_id']})
    (root/'runner.py').write_text('# synthetic lifecycle fixture only\n')
    (root/'trace.jsonl').write_text('{"frame":100,"time_s":0.0}\n')
    (root/'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":100,"native_frame":100,"time_s":0.0}\n')
    put(root/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})
    seal_capture(root,frames=1,restoration={'restored':True},errors=[],
                 encoder_exit_codes={'overview':0})
    record_native_exit(root)
    owner=acknowledge_owner_release(root,root/'owner-release.json',True)
    saved=json.loads((HERE/('proof-saved-'+suffix+'.log')).read_text())
    if owner['event']!='owner_released' or saved.get('recorded_only') is not True or saved.get('originals_preserved') is not True:
        raise ValueError('saved processing began without source-shaped release protocol')
    events=['capture_finished','encoders_closed','restoration_verified','native_exit',
            'owner_released','saved_processing_started']
    log=PROOFS/suffix/'lifecycle.log'
    log.write_text('case '+config['selected_case_id']+'\n'+'\n'.join(events)+
                   '\nsynthetic lifecycle with recorded-only replay receipt\n')
    return {'events':events,'exit_code':0,'log':str(log.relative_to(HERE)),
            'log_sha256':digest(log)}


def run():
    prepare_import()
    manifest=json.loads((HERE/'execution-manifest.saved-draft.json').read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(AID+'__')
        construction=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        fixtures=[outcome(config,suffix,kind,entry['construction_sha256'])
                  for kind in ('complete_motion','incomplete_motion','missing_evidence')]
        life=lifecycle(config,suffix)
        path=HERE/('physical-'+suffix+'-receipt.json')
        put(path,{'format':'worker-physical-preparation','case_id':entry['case_id'],
                  'construction_sha256':entry['construction_sha256'],
                  'fixtures':fixtures,'lifecycle':life,
                  'physical_acceptance_claimed':False,'legal_judgment':None})
        entry['physical_preparation']={'receipt':path.name,'sha256':digest(path)}
        print('physical',suffix,flush=True)
    (HERE/'execution-manifest.physical-draft.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true',required=True)
    parser.parse_args();run()
