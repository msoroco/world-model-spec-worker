"""Materialize four exact source-gated motor-vehicle sidewalk constructions."""
from __future__ import annotations

import json
from pathlib import Path
from sidewalk_case import CASES
from author_semantics import RECORDING

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='NRS-484B-450-1a'
CAMERAS=[{'name':name,'width':width,'height':height,
          'pose_strategy':strategy,'fov_deg':90}
         for name,width,height,strategy in (
             ('overview',1920,1080,'fixed road, sidewalk patch and parked vehicle'),
             ('approach',1280,720,'fixed road approach and optional traffic vehicle'),
             ('reference_corner',1280,720,'fixed curb/sidewalk boundary and body placement'),
             ('driver_reference',1280,720,'ego mounted parking approach view'))]
SOURCE_FILES=('runner.py','native_sidewalk.py','sidewalk_case.py','sidewalk_footprint.py',
              'site_review.py','analysis.py','tests/test_sidewalk_footprint.py')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    for i,item in enumerate(CASES):
        cid=AID+'__'+item.case_id
        config={'assignment_id':AID,'selected_case_id':cid,
                'supported_case_ids':[AID+'__'+x.case_id for x in CASES],
                'law_id':LAW,'cell_id':'C229462','actor':'motor_vehicle_driver',
                'rate_hz':20,'duration_s':45,'required_atoms':[],'source_packets':[],
                'cameras':CAMERAS,
                'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl',
                                       'position_key':'position_m','minimum_progress_m':4,
                                       'minimum_samples':2,'engineering_tolerances_not_legal':True},
                'case':{'case_id':cid,'requested_relation':item.relation,
                        'traffic_context':item.traffic_context,
                        'recording_description':RECORDING}}
        files=[{'path':name,'source':str((ROOT/name).relative_to(ROOT.parents[1])),
                'content':(ROOT/name).read_text(encoding='utf-8')} for name in SOURCE_FILES]
        files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
        construction={'law_id':LAW,'cell_id':'C229462','actor':'motor_vehicle_driver',
                      'case_id':cid,'entrypoint':'runner.py','files':files,
                      'measurement_plan':[{'name':'sidewalk_body_placement_and_context',
                                           'method':'analysis.analyze',
                                           'sources':['sidewalk-history.jsonl','sidewalk-site.json',
                                                      'video_frames.jsonl','trace.jsonl']}],
                      'recording_description':RECORDING,
                      'static_checks':['exact case, reviewed sidewalk and highway source identities',
                                       'vehicle body and activity readback; independent exception context'],
                      'termination_rules':['45 seconds of original 20 Hz approach and terminal parking'],
                      'mechanisms':['reviewed road and sidewalk geometry','ego parking route and body polygon',
                                    'optional conflict traffic actor with motion history',
                                    'four synchronized cameras','saved-only source-bound finalizer']}
        where=ROOT if i==0 else ROOT/'cases'/item.case_id
        write(where/'config.json',config);write(where/'construction.json',construction)


if __name__=='__main__':
    main()
