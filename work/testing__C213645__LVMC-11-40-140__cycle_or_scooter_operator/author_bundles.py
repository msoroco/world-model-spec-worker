"""Materialize four exact source-gated cycle driveway constructions."""
from __future__ import annotations

import json
from pathlib import Path
from driveway_case import CASES
from author_semantics import RECORDING

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='LVMC-11-40-140'
CAMERAS=[{'name':name,'width':width,'height':height,
          'pose_strategy':strategy,'fov_deg':90}
         for name,width,height,strategy in (
             ('overview',1920,1080,'fixed driveway, sidewalk area and road'),
             ('approach',1280,720,'fixed cycle approach and stopping point'),
             ('reference_corner',1280,720,'fixed sidewalk edge and pedestrian conflict region'),
             ('driver_reference',1280,720,'cycle mounted forward reference'))]
SOURCE_FILES=('runner.py','native_driveway.py','driveway_case.py','driveway_sidewalk.py',
              'site_review.py','analysis.py','tests/test_driveway_sidewalk.py')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    for i,item in enumerate(CASES):
        cid=AID+'__'+item.case_id
        config={'assignment_id':AID,'selected_case_id':cid,
                'supported_case_ids':[AID+'__'+x.case_id for x in CASES],
                'law_id':LAW,'cell_id':'C213645','actor':'cycle_or_scooter_operator',
                'rate_hz':20,'duration_s':45,'required_atoms':[],'source_packets':[],
                'cameras':CAMERAS,
                'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl',
                                       'position_key':'position_m','minimum_progress_m':4,
                                       'minimum_samples':2,'engineering_tolerances_not_legal':True},
                'case':{'case_id':cid,'requested_stop':item.stop,
                        'requested_pedestrian':item.pedestrian,
                        'requested_yield':item.yield_to_pedestrian,
                        'recording_description':RECORDING}}
        files=[{'path':name,'source':str((ROOT/name).relative_to(ROOT.parents[1])),
                'content':(ROOT/name).read_text(encoding='utf-8')} for name in SOURCE_FILES]
        files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
        construction={'law_id':LAW,'cell_id':'C213645','actor':'cycle_or_scooter_operator',
                      'case_id':cid,'entrypoint':'runner.py','files':files,
                      'measurement_plan':[{'name':'driveway_stop_pedestrian_yield',
                                           'method':'analysis.analyze',
                                           'sources':['driveway-history.jsonl','driveway-site.json',
                                                      'video_frames.jsonl','trace.jsonl']}],
                      'recording_description':RECORDING,
                      'static_checks':['exact case, reviewed district, driveway and sidewalk identity',
                                       'qualifying vehicle, pre-entry stop and pedestrian motion readback'],
                      'termination_rules':['45 seconds of original 20 Hz approach, crossing and passage'],
                      'mechanisms':['reviewed residence driveway and sidewalk continuation',
                                    'cycle route, stop and pedestrian conflict controller',
                                    'four synchronized cameras','saved-only source-bound finalizer']}
        where=ROOT if i==0 else ROOT/'cases'/item.case_id
        write(where/'config.json',config);write(where/'construction.json',construction)


if __name__=='__main__':
    main()
