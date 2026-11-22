"""Synthetic three-outcome U-turn and Native ownership protocol proof."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(path,config,construction,kind):
    path.mkdir()
    write(path/'config.json',config)
    write(path/'construction.json',construction)
    (path/'runner.py').write_text(next(f['content'] for f in construction['files']
                                      if f['path']=='runner.py'))
    write(path/'acquisition-provenance.json',{
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})
    if kind=='missing_evidence':return
    trace=[];mapping=[];events=[]
    for index in range(9):
        frame=200+index;time_s=index/20;x=float(index)
        heading=180.*index/8 if kind=='complete_motion' else 0.
        body=[[x-.2,-.2,0.],[x-.2,.2,0.],
              [x+.2,-.2,0.],[x+.2,.2,0.]]
        trace.append({'frame':frame,'time_s':time_s,'position':{'x':x,'y':0.,'z':0.},
                      'position_m':[x,0.,0.],'heading_deg':heading,'speed_mps':1.})
        mapping.append({'video_frame':index,'carla_frame':frame,'time_s':time_s})
        events.append({'frame':frame,'time_s':time_s,
                       'operator_body_vertices_m':body,'heading_deg':heading})
    for name,rows in [('trace.jsonl',trace),('video_frames.jsonl',mapping),
                      ('phase-events.jsonl',events)]:
        (path/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    from worker_exchange.native_output import physical_result,seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release,copy_sources)
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==args.case)
    construction=json.loads((ROOT/entry['construction']).read_text())
    config=json.loads(next(f['content'] for f in construction['files']
                           if f['path']=='config.json'))
    suffix=args.case.removeprefix(ROOT.name+'__')
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    for kind,expected in [('complete_motion','met'),
                          ('incomplete_motion','not_met'),
                          ('missing_evidence','unverified')]:
        folder=output/kind;fixture(folder,config,construction,kind)
        result=physical_result(folder,{'target_checks':[{
            'target':'observed original body 180 degree reversal',
            'requested':True,'measured':kind=='complete_motion',
            'method':'synthetic source-shaped 20 Hz body and heading samples',
            'tolerance':0,'matched':kind=='complete_motion',
            'physical_cause_confirmed':False,
            'cause_evidence':'diagnostic fixture only'}]})
        if (result['physical_checks']['maneuver']['status']!=expected or
                result['maneuver_completed']!=(expected=='met')):
            raise ValueError('Physical outcome mismatch: '+kind)
        write(ROOT/('physical-'+suffix+'-'+kind+'.json'),result)
        print(kind,expected,sorted(result['physical_checks']['maneuver']['sources']))
    complete=output/'complete_motion'
    seal=seal_capture(complete,frames=9,
        restoration={'restored':True,'settings_readback':'CPU protocol fixture'},
        errors=[],encoder_exit_codes={'diagnostic':0})
    exit_receipt=record_native_exit(complete)
    owner=acknowledge_owner_release(complete,complete/'owner-release.json',True)
    stage=output/'saved_stage';stage.mkdir();copy_sources(complete,stage)
    if (exit_receipt['capture_seal_sha256']!=sha(complete/'capture-seal.json') or
            owner['native_exit_sha256']!=sha(complete/'native-exit.json')):
        raise ValueError('Lifecycle source binding failed')
    print('lifecycle',*seal['events'],'native_exit','owner_released',
          'saved_processing_started')


if __name__=='__main__':main()
