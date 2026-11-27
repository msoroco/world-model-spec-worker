"""Create case-specific synthetic compatibility sources; never original evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from safety_zone import CASES, body_center, between_zone_curb, signed_end_station

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def write(path,value):
    path.write_text(json.dumps(value,separators=(',',':'),ensure_ascii=False)+'\n',encoding='utf-8')

def scene(case):
    zone=[0,0,20,2]
    body=[9,3,11,4.5]
    if case.placement=='outside':body=[9,5.5,11,7]
    elif case.placement=='end_band':
        x=-case.offset_m if case.end=='west' else 20+case.offset_m
        body=[x-1,3,x+1,4.5]
    center=body_center(body)
    scene={'cell_id':'C229455','actor':'motor_vehicle_driver','driver_present':True,
      'motor_vehicle':True,'highway_public_access':True,
      'safety_zone_designated_pedestrian_exclusive':True,
      'safety_zone_set_apart_visible':True,
      'safety_zone_marking_or_sign_source_sha256':'synthetic-marking',
      'placement':case.placement,'end':case.end,'activity':case.activity,
      'exception':case.exception,'zone_rect_m':zone,'target_body_rect_m':body,
      'adjacent_curb_y_m':5,'west_end_curb_point_m':[0,5],
      'east_end_curb_point_m':[20,5],'vehicle_target_xy':center,
      'vehicle_start_xy':[center[0]-12,center[1]],
      'traffic_start_xy':[-20,-2],'traffic_target_xy':[35,-2],
      'vehicle_route_xy':[[center[0]-12,center[1]],center],
      'traffic_route_xy':[[-20,-2],[35,-2]],
      'conflicting_traffic_id':'synthetic-traffic','authority_record_id':'synthetic-authority',
      'highway_status':'synthetic','official_designation':'synthetic',
      'visible_marking':'synthetic','curb_adjacency':'synthetic',
      'driver_identity':'synthetic','vehicle_class':'synthetic',
      'traffic_conflict_necessity':'unresolved','law_compliance':'unresolved',
      'officer_direction':'unresolved','official_device_direction':'unresolved'}
    for name in ('map','highway','zone','curb','designation','vehicle','driver','route',
                 'traffic','activity','exception'):
        scene[name+'_source_sha256']='synthetic-'+name
    return scene

def main():
    base=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    mapping=[json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for case in CASES:
        spec=json.loads(json.dumps(base))
        for name in ('alley_context.json','body_history.jsonl','speed_samples.jsonl'):
            spec['files'].pop(name,None)
        data=scene(case)
        station=signed_end_station(body_center(data['target_body_rect_m']),
            data['west_end_curb_point_m'],data['east_end_curb_point_m'],case.end)
        corridor=between_zone_curb(data['target_body_rect_m'],data['zone_rect_m'],
            data['adjacent_curb_y_m'])
        history=[]
        for row in mapping:
            item={'original_frame':row['carla_frame'],'time_s':row['time_s'],
              'vehicle_id':'synthetic-ego','traffic_id':'synthetic-traffic',
              'activity':case.activity,'exception':case.exception,
              'vehicle_body_rect_m':data['target_body_rect_m'],
              'signed_end_station_m':station,'between_zone_curb':corridor,
              'vehicle_speed_mps':0.0,'traffic_speed_mps':4.0}
            for name in ('frame','vehicle_motion','vehicle_body','zone','curb',
                         'activity','exception','traffic_motion'):
                item[name+'_source_sha256']=data.get(name+'_source_sha256','synthetic-'+name)
            history.append(item)
        spec['files']['safety-zone-site.json']=json.dumps({'scene':data})+'\n'
        spec['files']['safety-zone-history.jsonl']=''.join(json.dumps(row)+'\n' for row in history)
        spec['files']['diagnostic-source-note.json']=json.dumps({
          'source_kind':'synthetic_diagnostic_fixture','accepted_original_source':False,
          'case_id':ROOT.name+'__'+case.case_id})+'\n'
        spec['files']['carla_recorder.log']='synthetic diagnostic recorder placeholder\n'
        source=ROOT/('diagnostic-'+case.case_id+'.json');write(source,spec)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        name=str(source.relative_to(REPO))
        recipe={'format':'worker-fixture-recipe',
          'sources':[{'path':'diagnostic-input.json','source':name,'sha256':digest}],
          'generator':{'source':name,'sha256':digest}}
        write(ROOT/('diagnostic-'+case.case_id+'-recipe.json'),recipe)
if __name__=='__main__':main()
