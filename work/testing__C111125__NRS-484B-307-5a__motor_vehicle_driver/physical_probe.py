"""CPU proof of the intersection-clearance criterion and closure ordering."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(path,config,construction,kind):
    path.mkdir();write(path/'config.json',config);write(path/'construction.json',construction)
    runner=next(f['content'] for f in construction['files'] if f['path']=='runner.py')
    (path/'runner.py').write_text(runner)
    write(path/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
                                             'diagnostic_fixture':True})
    if kind=='missing_evidence':return
    xs=([-12,-9,-6,-3,0,3,6,9,12] if kind=='complete_motion' else
        [-12,-11.9,-11.8,-11.7,-11.6,-11.5,-11.4,-11.3,-11.2])
    motion=[];trace=[];mapping=[]
    for index,x in enumerate(xs):
        frame=200+index;time_s=index/20
        motion.append({'frame':frame,'time_s':time_s,
                       'body_vertices_m':[[x,-.5,0],[x+1,-.5,0],
                                          [x+1,.5,0],[x,.5,0]]})
        trace.append({'frame':frame,'time_s':time_s,'position':{'x':x+.5,'y':0,'z':0},
                      'position_m':[x+.5,0,0],'heading_deg':0,'speed_mps':1})
        mapping.append({'video_frame':index,'carla_frame':frame,'time_s':time_s})
    for name,rows in [('ego-body-history.jsonl',motion),('trace.jsonl',trace),
                      ('video_frames.jsonl',mapping)]:
        (path/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    from worker_exchange.native_output import physical_result,seal_capture
    from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,copy_sources
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==args.case)
    construction=json.loads((ROOT/entry['construction']).read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    label='yield' if '__yield_' in args.case else 'clear'
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    for kind,expected in [('complete_motion','met'),('incomplete_motion','not_met'),
                          ('missing_evidence','unverified')]:
        folder=root/kind;fixture(folder,config,construction,kind)
        result=physical_result(folder,{'target_checks':[{'target':'observed intersection clearance',
             'requested':True,'measured':kind=='complete_motion','method':'CPU source-bound body path',
             'tolerance':0,'matched':kind=='complete_motion','physical_cause_confirmed':False,
             'cause_evidence':'diagnostic body history'}]})
        if result['physical_checks']['maneuver']['status']!=expected or result['maneuver_completed']!=(expected=='met'):
            raise ValueError('Physical outcome mismatch: '+kind)
        write(ROOT/('physical-'+label+'-'+kind+'.json'),result)
        print(kind,expected,'sources',sorted(result['physical_checks']['maneuver']['sources']))
    complete=root/'complete_motion'
    seal=seal_capture(complete,frames=9,restoration={'restored':True,
        'settings_readback':'CPU protocol fixture'},errors=[],encoder_exit_codes={'diagnostic':0})
    exit_receipt=record_native_exit(complete)
    owner=acknowledge_owner_release(complete,complete/'owner-release.json',True)
    stage=root/'saved_stage';stage.mkdir();copy_sources(complete,stage)
    if exit_receipt['capture_seal_sha256']!=sha(complete/'capture-seal.json') or owner['native_exit_sha256']!=sha(complete/'native-exit.json'):
        raise ValueError('Lifecycle source binding failed')
    print('lifecycle',*seal['events'],'native_exit','owner_released','saved_processing_started')


if __name__=='__main__':main()
