"""CPU source-bound motion and lifecycle probes; no Native provenance claim."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def fixture(folder,config,construction,kind):
    folder.mkdir()
    write(folder/'config.json',config)
    write(folder/'construction.json',construction)
    for item in construction['files']:
        if item['path']=='runner.py':(folder/'runner.py').write_text(item['content'])
    write(folder/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'physical_acceptance_claimed':False})
    if kind=='missing_evidence':return
    trace=[];mapping=[];history=[]
    for index in range(9):
        frame=100+index;time_s=index/20
        if kind=='complete_motion':
            x=1.5*index;y=-2+1.5*index;heading=90*index/8
        else:
            x=.1*index;y=-2+.1*index;heading=15*index/8
        body=[[x-.5,y-.5,0],[x+.5,y-.5,0],[x+.5,y+.5,0],[x-.5,y+.5,0]]
        trace.append({'frame':frame,'time_s':time_s,'position':{'x':x,'y':y,'z':0},
                      'position_m':[x,y,0],'heading_deg':heading,'speed_mps':1})
        mapping.append({'video_frame':index,'carla_frame':frame,'time_s':time_s})
        history.append({'frame':frame,'time_s':time_s,'ego_body_vertices_m':body,
                        'heading_deg':heading,'left_signal':index>=1})
    (folder/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in trace))
    (folder/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in mapping))
    (folder/'turn-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in history))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    from worker_exchange.native_output import physical_result,seal_capture
    from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,copy_sources
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==args.case)
    construction=json.loads((ROOT/entry['construction']).read_text())
    config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
    outcomes={}
    for kind,expected in [('complete_motion','met'),('incomplete_motion','not_met'),('missing_evidence','unverified')]:
        folder=root/kind;fixture(folder,config,construction,kind)
        result=physical_result(folder,{'target_checks':[{'target':'turn','requested':True,
                       'measured':kind=='complete_motion','method':'CPU sampled motion',
                       'tolerance':0,'matched':kind=='complete_motion',
                       'physical_cause_confirmed':False,'cause_evidence':'diagnostic source rows'}]})
        actual=result['physical_checks']['maneuver']['status']
        if actual!=expected or result['maneuver_completed']!=(expected=='met'):
            raise ValueError('Physical fixture outcome mismatch: '+kind+' '+actual)
        if expected=='met' and not result['realized_observables']:
            raise ValueError('Complete motion lost measured observations')
        path=ROOT/('physical-'+('unsignaled' if '__unsignaled_' in args.case else 'signaled')+'-'+kind+'.json')
        write(path,result)
        outcomes[kind]={'result':path.name,'result_sha256':sha(path),
                        'status':actual}
        print(kind,actual,'sources',sorted(result['physical_checks']['maneuver']['sources']))
    complete=root/'complete_motion'
    seal=seal_capture(complete,frames=9,restoration={'restored':True,
        'settings_readback':'CPU lifecycle protocol fixture'},errors=[],encoder_exit_codes={'diagnostic':0})
    exited=record_native_exit(complete)
    released=acknowledge_owner_release(complete,complete/'owner-release.json',True)
    stage=root/'saved_stage';stage.mkdir();copy_sources(complete,stage)
    if exited['capture_seal_sha256']!=sha(complete/'capture-seal.json') or released['native_exit_sha256']!=sha(complete/'native-exit.json'):
        raise ValueError('Lifecycle hash binding failed')
    if seal['events']!=['capture_finished','encoders_closed','restoration_verified']:
        raise ValueError('Lifecycle ordering failed')
    print('lifecycle',*seal['events'],'native_exit','owner_released','saved_processing_started')
    print('case',args.case,'diagnostic_only',True)


if __name__=='__main__':main()
