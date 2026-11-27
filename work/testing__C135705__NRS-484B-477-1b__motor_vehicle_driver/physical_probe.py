"""Exercise source-bound alley-width physical outcomes and Native closure."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from width_measurement import measure_saved

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
KINDS=('complete_motion','incomplete_motion','missing_evidence')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matched(slug,measured):
    width=measured['minimum_available_continuous_width_ft']
    expected={'width_9_9ft':9.9,'width_10_0ft':10.,'width_10_1ft':10.1,
              'ordinance_otherwise':9.9}
    if slug in expected:
        return abs(width-expected[slug])<=.05 and (slug!='ordinance_otherwise' or measured['ordinance_status']=='otherwise_provides')
    if slug=='other_vehicle_close':return width<10 and all(row['other_vehicle_count']>0 for row in measured['held_samples'])
    if slug=='other_vehicle_far':return width>=9.95 and all(row['other_vehicle_count']>0 for row in measured['held_samples'])
    raise ValueError('unselected alley-width case')


def run(case_id,kind,output):
    plan=json.loads((HERE/'case-plan.json').read_text())
    if kind not in KINDS or case_id not in {row['case_id'] for row in plan['cases']}:
        raise ValueError('exact case or physical fixture kind missing')
    scratch=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if REPO/'.runtime-work' not in scratch.parents:
        raise ValueError('physical scratch must live under .runtime-work')
    slug=case_id.removeprefix(HERE.name+'__')
    spec=json.loads((HERE/('diagnostic-'+slug+'.json')).read_text())
    with tempfile.TemporaryDirectory(dir=scratch) as td:
        stage=Path(td)
        for name,data in spec['files'].items():
            if name.startswith('original-attempt/'):
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(data)
        source=stage/'original-attempt'
        if kind=='incomplete_motion':
            path=source/'width_history.json'
            data=json.loads(path.read_text())
            for row in data['samples']:row['phase']='approach'
            path.write_text(json.dumps(data,sort_keys=True)+'\n')
            inventory=json.loads((source/'inventory.json').read_text())
            inventory['sources']['width_history']['sha256']=sha(path)
            (source/'inventory.json').write_text(json.dumps(inventory,sort_keys=True)+'\n')
        elif kind=='missing_evidence':
            (source/'width_history.json').unlink()
        measured=None;error=None
        try:
            measured=measure_saved(source,case_id,expected_frames=9)
            status='met' if matched(slug,measured) else 'not_met'
        except (ValueError,FileNotFoundError) as failure:
            error=str(failure)
            if kind=='incomplete_motion' and 'parked hold absent' in error:
                status='not_met'
            elif kind=='missing_evidence' and 'width_history' in error:
                status='unverified'
            else:raise
        expected={'complete_motion':'met','incomplete_motion':'not_met',
                  'missing_evidence':'unverified'}[kind]
        if status!=expected:
            raise ValueError('physical diagnostic outcome differs: '+kind+' '+status)
        result={'case_id':case_id,
            'physical_checks':{'maneuver':{'status':status,
                'method':'source-bound original parked hold and continuous alley-width remeasurement',
                'sources':{name:sha(source/name) for name in
                    ('alley_geometry.json','frame_map.json','width_history.json') if (source/name).is_file()},
                'error':error,'legal_free_movement_claimed':False}},
            'maneuver_completed':status=='met',
            'realized_observables':{} if measured is None else {
                'available_continuous_width_ft':{'value':measured['minimum_available_continuous_width_ft'],
                    'unit':'ft','method':'surveyed cross-section/body intersection',
                    'statistic':'minimum','time_window':'parked hold',
                    'reference':'original-attempt/width_history.json'}},
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'physical_acceptance_claimed':False,'legal_judgment':None}
        Path(output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        lifecycle=None
        if kind=='complete_motion':
            sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,copy_sources
            (stage/'runner.py').write_text((HERE/'runner.py').read_text())
            (stage/'construction.json').write_text((HERE/'cases'/slug/'construction.json').read_text())
            (stage/'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
                'physical_acceptance_claimed':False})+'\n')
            frames=json.loads((source/'frame_map.json').read_text())['frames']
            (stage/'trace.jsonl').write_text(''.join(json.dumps({
                'frame':row['frame'],'time_s':row['time_s'],'speed_mps':0})+'\n' for row in frames))
            (stage/'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame':i,'carla_frame':row['frame'],'native_frame':row['frame'],
                'time_s':row['time_s']})+'\n' for i,row in enumerate(frames)))
            seal=seal_capture(stage,frames=9,restoration={'restored':True,
                'settings_readback':'synthetic CPU closure fixture'},errors=[],
                encoder_exit_codes={'fixture':0})
            native_exit=record_native_exit(stage)
            owner=acknowledge_owner_release(stage,stage/'owner-release.json',True)
            with tempfile.TemporaryDirectory(dir=scratch) as saved:copy_sources(stage,Path(saved))
            if native_exit['capture_seal_sha256']!=sha(stage/'capture-seal.json') or owner['native_exit_sha256']!=sha(stage/'native-exit.json'):
                raise ValueError('Native alley-width lifecycle closure differs')
            lifecycle=seal['events']+['native_exit','owner_released','saved_processing_started']
        return {'case_id':case_id,'kind':kind,'status':status,
                'diagnostic_fixture':True,'physical_acceptance_claimed':False,
                'lifecycle':lifecycle}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',choices=KINDS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.case,args.kind,args.output),sort_keys=True))


if __name__=='__main__':main()
