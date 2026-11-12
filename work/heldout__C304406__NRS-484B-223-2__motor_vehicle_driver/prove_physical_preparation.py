"""CPU source-protocol and ownership lifecycle proof for nine three-lane cases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical, default_descriptor
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def config(entry):
    construction=json.loads((HERE/entry['construction']).read_text())
    return json.loads(next(row['content'] for row in construction['files'] if row['path']=='config.json'))


def prove(manifest,selected=None):
    entries=manifest['cases']
    cases=[entry['case_id'] for entry in entries]
    if selected and selected not in cases:raise ValueError('Unknown exact physical fixture case')
    configs=[config(entry) for entry in entries]
    descriptors=[default_descriptor(cfg) for cfg in configs]
    if (len({json.dumps(desc,sort_keys=True) for desc in descriptors})!=1 or
            any(cfg.get('duration_s')!=8 or cfg.get('rate_hz')!=20 for cfg in configs)):
        raise ValueError('Physical source protocol is not shared across exact cases')
    cfg=configs[0]
    outcome_names=('complete_motion','incomplete_motion','missing_evidence')
    results=[];log=[]
    for kind in outcome_names:
        with tempfile.TemporaryDirectory(prefix='c304406-physical-',dir='/tmp') as temp:
            root=Path(temp)
            put(root/'config.json',cfg)
            frames=[{'video_frame':i,'carla_frame':1000+i,'time_s':round(i/20,5)}
                    for i in range(160)]
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
            if kind!='missing_evidence':
                end=40 if kind=='complete_motion' else 4
                trace=[{'frame':1000+i,'time_s':round(i/20,5),
                        'position_m':[end*i/159,0.0,0.0]} for i in range(160)]
                (root/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
            assessed=assess_physical(root,cfg)
            expected={'complete_motion':'met','incomplete_motion':'not_met',
                      'missing_evidence':'unverified'}[kind]
            actual=assessed['physical_checks']['maneuver']['status']
            if actual!=expected:raise ValueError('Source motion outcome differs: '+kind+' '+actual)
            result={'format':'worker-physical-source-protocol-fixture',
                    'fixture_kind':kind,'diagnostic_fixture':True,
                    'shared_cases':cases,'provenance_kind':'native' if kind=='complete_motion' else 'diagnostic',
                    'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                    'physical_checks':assessed['physical_checks'],
                    'maneuver_completed':assessed['maneuver_completed'],
                    'realized_observables':assessed['realized_observables']}
            name='physical-'+kind+'.json';put(HERE/name,result)
            results.append((kind,name,digest(HERE/name)))
            log.append(f'{kind}: {actual}; source-bound 160-frame protocol, engineering travel-progress criterion; diagnostic only')
    with tempfile.TemporaryDirectory(prefix='c304406-lifecycle-',dir='/tmp') as temp:
        attempt=Path(temp)
        first=entries[0]
        (attempt/'construction.json').write_bytes((HERE/first['construction']).read_bytes())
        (attempt/'runner.py').write_bytes((HERE/'runner.py').read_bytes())
        seal={'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{},'native_revision':{'construction_sha256':digest(attempt/'construction.json'),
                 'runner_sha256':digest(attempt/'runner.py')}}
        put(attempt/'capture-seal.json',seal)
        try:acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        except ValueError as error:
            if 'has not exited' not in str(error):raise
        else:raise AssertionError('Premature owner release accepted')
        receipt=record_native_exit(attempt)
        if receipt['event']!='native_exit':raise ValueError('Native exit missing')
        owner=acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        if owner['event']!='owner_released':raise ValueError('Owner release missing')
        _closure(attempt,attempt/'owner-release.json','native',False)
    events=seal['events']+['native_exit','owner_released','saved_processing_started']
    log.append('Lifecycle: '+' -> '.join(events)+'; premature owner release rejected')
    log_name='physical-source-protocol.log'
    (HERE/log_name).write_text('\n'.join(log)+'\n')
    log_sha=digest(HERE/log_name)
    for entry in entries:
        if selected and entry['case_id']!=selected:continue
        case=entry['case_id'];short=case.rsplit('__',1)[-1]
        command=f'.venv-cpu/bin/python work/{HERE.name}/prove_physical_preparation.py --case {case}'
        fixtures=[{'kind':kind,'command':command,'exit_code':0,'log':log_name,
                   'log_sha256':log_sha,'result':name,'result_sha256':checksum}
                  for kind,name,checksum in results]
        proof={'format':'worker-physical-preparation-proof','case_id':case,
               'construction_sha256':entry['construction_sha256'],
               'fixture_scope':'shared 20 Hz source protocol; not case-specific realized Native maneuver',
               'fixtures':fixtures,
               'lifecycle':{'events':events,'exit_code':0,'log':log_name,'log_sha256':log_sha}}
        name=short+'-physical-preparation.json';put(HERE/name,proof)
        entry['physical_preparation']={'receipt':name,'sha256':digest(HERE/name)}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args()
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    prove(manifest,args.case)


if __name__=='__main__':main()
