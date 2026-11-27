"""Materialize twelve exact source-gated 450(1)(h) constructions."""
from __future__ import annotations
import json
from pathlib import Path
from safety_zone import CASES
from author_plan import CHANNELS

ROOT=Path(__file__).resolve().parent
AID=ROOT.name
LAW='NRS-484B-450-1h'
FILES=('runner.py','native_zone.py','site_review.py','safety_zone.py','analysis.py',
       'tests/test_safety_zone.py')
CAMERAS=[{'name':name,'width':width,'height':height,'pose_strategy':strategy,'fov_deg':90}
 for name,width,height,strategy in (
  ('overview',1920,1080,'fixed entire official zone and adjacent curb'),
  ('approach',1280,720,'fixed vehicle approach and curb-end station'),
  ('reference_corner',1280,720,'fixed curb point opposite selected zone end and body'),
  ('driver_reference',1280,720,'ego mounted visible zone marking/sign'))]
CONTEXT=('highway_status','official_designation','visible_marking','curb_adjacency',
         'driver_identity','vehicle_class','traffic_conflict_necessity',
         'law_compliance','officer_direction','official_device_direction')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def recording():
    return {'channels':[{'name':name,'unit':'structured original record','sampling_rate_hz':20,
       'method':'Original Native frame acquisition and saved-only extraction',
       'time_window':'approach through terminal halt','reference_frame':'original CARLA world frame and timestamp',
       'uncertainty':'20 Hz sampling, actor body vertex and source geometry'} for name in CHANNELS],
      'context_inputs':[{'name':name,'unit':'reviewed original source packet',
        'method':'Independent original highway/zone/curb/authority source binding'} for name in CONTEXT],
      'limitations':['Zone markers alone do not establish an officially designated safety zone.',
        'Original body-to-opposite-curb-end station retains geometry without resolving legal distance convention.',
        'Physical marking visibility, exception applicability and actual pixels require independent review.']}

def main():
    ids=[AID+'__'+case.case_id for case in CASES]
    description=recording()
    for index,case in enumerate(CASES):
        cid=ids[index]
        config={'assignment_id':AID,'selected_case_id':cid,'supported_case_ids':ids,
          'law_id':LAW,'cell_id':'C229455','actor':'motor_vehicle_driver',
          'rate_hz':20,'duration_s':45,'engineering_throttle':.25,
          'engineering_braking_factor':5.0,'required_atoms':[],'source_packets':[],
          'cameras':CAMERAS,
          'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl',
              'position_key':'position_m','minimum_progress_m':4,'minimum_samples':2,
              'engineering_tolerances_not_legal':True},
          'case':{'case_id':cid,'placement':case.placement,'end':case.end,
                  'offset_m':case.offset_m,'halt_activity':case.activity,
                  'exception_context':case.exception,'recording_description':description}}
        files=[{'path':name,'source':str((ROOT/name).relative_to(ROOT.parents[1])),
                'content':(ROOT/name).read_text(encoding='utf-8')} for name in FILES]
        files.append({'path':'config.json','content':json.dumps(config,indent=2,ensure_ascii=False)+'\n'})
        construction={'law_id':LAW,'cell_id':'C229455','actor':'motor_vehicle_driver',
            'case_id':cid,'entrypoint':'runner.py','files':files,
            'measurement_plan':[{'name':'safety_zone_body_station_and_exception_context',
              'method':'analysis.analyze','sources':['safety-zone-site.json',
              'safety-zone-history.jsonl','video_frames.jsonl','trace.jsonl']}],
            'recording_description':description,
            'static_checks':['exact case and original reviewed zone source hashes',
               'official designation, visible markings and map hash',
               'physical zone edge markers, adjacent curb and both opposite end references',
               'ego body footprint, route, halt and independently sourced exception context'],
            'termination_rules':['45 seconds at 20 Hz with approach and terminal halt',
               'failed frame join, source readback, cleanup or restoration rejects capture'],
            'mechanisms':['reviewed original zone and curb source gate',
               'physical boundary markers and motor vehicles',
               'ego halt and traffic controllers','four synchronized cameras and original frame map',
               'saved-only source-bound finalizer']}
        folder=ROOT if index==0 else ROOT/'cases'/case.case_id
        write(folder/'config.json',config);write(folder/'construction.json',construction)

if __name__=='__main__':main()
