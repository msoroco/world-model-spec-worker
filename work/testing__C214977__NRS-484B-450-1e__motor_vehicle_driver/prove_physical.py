"""CPU protocol fixtures for physical completion and Native ownership ordering.

All generated motion is labeled synthetic and cannot establish a real capture.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import (record_native_exit,
                                               acknowledge_owner_release, _closure,
                                               copy_sources)


def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,separators=(',',':'))+'\n')


def motion(construction, output, mode):
    bundle=json.loads(Path(construction).read_text())
    config=json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
    root=Path(output)
    root.mkdir(parents=True,exist_ok=False)
    _write(root/'config.json',config)
    _write(root/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
                                                'diagnostic_fixture':True})
    if mode != 'missing_evidence':
        with (root/'trace.jsonl').open('x') as trace, (root/'video_frames.jsonl').open('x') as frame_map:
            for i in range(900):
                x=200*i/899 if mode=='complete_motion' else 0.0
                trace.write(json.dumps({'frame':i,'time_s':i*.05,'position_m':[x,0.0,0.0],
                                        'heading_deg':0.0,'speed_mps':0.0})+'\n')
                frame_map.write(json.dumps({'video_frame':i,'carla_frame':i,
                                            'native_frame':i,'time_s':i*.05})+'\n')
    result=physical_result(root,{'target_checks':[{'target':'diagnostic motion','requested':True,
        'measured':True,'matched':True,'method':'synthetic fixture target','tolerance':0,
        'physical_cause_confirmed':False,'cause_evidence':'fixture only'}]})
    expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[mode]
    if result['physical_checks']['maneuver']['status']!=expected:
        raise ValueError('physical fixture status differs: '+mode)
    if result['provenance_kind']!='synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise ValueError('fixture provenance changed')
    _write(root/'result.json',result)
    print(json.dumps({'case_id':bundle['case_id'],'fixture':mode,'maneuver':expected,
                      'physical_acceptance_claimed':False}))


def lifecycle(construction,output):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=False)
    bundle=json.loads(Path(construction).read_text())
    _write(root/'construction.json',bundle)
    (root/'runner.py').write_text(next(f['content'] for f in bundle['files'] if f['path']=='runner.py'))
    _write(root/'config.json',json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json')))
    _write(root/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
                                                'diagnostic_fixture':True})
    (root/'trace.jsonl').write_text('{"frame":0,"time_s":0}\n')
    (root/'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":0,"time_s":0}\n')
    seal_capture(root,frames=1,restoration={'restored':True},errors=[],encoder_exit_codes={},
                 context={'scope':'diagnostic lifecycle fixture; no real restoration'})
    native_exit=record_native_exit(root)
    _write(root/'native-exit.json',native_exit)
    receipt=acknowledge_owner_release(root,root/'owner-release.json',True)
    _closure(root,root/'owner-release.json','synthetic_fixture',True)
    stage=Path(str(root)+'-saved-stage');stage.mkdir()
    copy_sources(root,stage)
    if not (stage/'trace.jsonl').is_file() or receipt['event']!='owner_released':
        raise ValueError('saved stage started before owner release')
    events=['capture_finished','encoders_closed','restoration_verified',
            'native_exit','owner_released','saved_processing_started']
    _write(root/'lifecycle-result.json',{'events':events,'diagnostic_fixture':True,
                                          'physical_acceptance_claimed':False})
    print(json.dumps({'case_id':bundle['case_id'],'events':events,'scope':'CPU lifecycle fixture'}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--construction',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--mode',choices=('complete_motion','incomplete_motion',
                                         'missing_evidence','lifecycle'),required=True)
    args=parser.parse_args()
    if args.mode=='lifecycle':lifecycle(args.construction,args.output)
    else:motion(args.construction,args.output,args.mode)


if __name__=='__main__':main()
