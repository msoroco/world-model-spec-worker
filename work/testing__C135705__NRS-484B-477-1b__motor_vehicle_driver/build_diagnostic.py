"""Build nine-frame source-shaped alley-width CPU fixtures only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SOURCE={"path":"diagnostic/original-source.json","sha256":"d"*64}


def dump(value):return json.dumps(value,sort_keys=True,indent=2)+"\n"
def sha(data):return hashlib.sha256(data.encode()).hexdigest()


def build():
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    base=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    mapping=[json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines() if line.strip()]
    if len(mapping)!=9:raise ValueError('generic Core/video smoke fixture changed')
    for entry in manifest['cases']:
        case_id=entry['case_id'];slug=case_id.removeprefix(HERE.name+'__')
        spec=json.loads(json.dumps(base))
        files=spec['files']
        frames=[{'frame':row['carla_frame'],'time_s':row['time_s'],'video_frame':i}
                for i,row in enumerate(mapping)]
        target={'width_9_9ft':9.9,'width_10_0ft':10.0,'width_10_1ft':10.1,
                'ordinance_otherwise':9.9}.get(slug,10.0)
        ego_y=5-target/3.280839895013123
        ego=[[49,0],[51,0],[51,ego_y],[49,ego_y]]
        other=[[49,3.2],[51,3.2],[51,5],[49,5]] if slug=='other_vehicle_close' else \
              [[70,3.2],[72,3.2],[72,5],[70,5]] if slug=='other_vehicle_far' else None
        geometry={"case_id":case_id,"source_kind":"original_native_geometry",
                  "alley_kind":"other_alley","public_highway_status":True,
                  "cul_de_sac":False,"start_connected":True,"end_connected":True,
                  "ordinance_status":"otherwise_provides" if slug=='ordinance_otherwise' else 'unresolved',
                  "map_sha256":sha(files['road.xodr']),"ego_vehicle_id":"ego",
                  "centerline_start_m":[0,2.5],"centerline_end_m":[100,2.5],
                  "parking_station_m":50,"ego_length_m":4.5,"ego_width_m":1.8,
                  "cross_sections":[{'station_m':s,'left_xy_m':[s,0],
                                     'right_xy_m':[s,5],'source':SOURCE} for s in (50,51)]}
        for name in ('public_highway_source','city_block_source','rear_access_source',
                     'abutting_property_source','through_connection_source','jurisdiction_source',
                     'ordinance_source','survey_source'):
            geometry[name]=SOURCE
        history=[{'frame':frame['frame'],'time_s':frame['time_s'],'source':SOURCE,
                  'phase':'parked_hold' if i>=3 else 'approach',
                  'ego_body_polygon_m':ego,
                  'other_body_polygons_m':[other] if other else [],
                  'ego_vehicle_id':'ego','other_vehicle_id':'other' if other else None,
                  'speed_mps':0 if i>=3 else 2} for i,frame in enumerate(frames)]
        source_values={'frame_map':{'frames':frames},'alley_geometry':geometry,
                       'width_history':{'case_id':case_id,'source_kind':'original_native','samples':history}}
        inventory={'case_id':case_id,'source_kind':'original_native','frame_count':9,
                   'diagnostic_fixture':True,'map_sha256':geometry['map_sha256'],
                   'sources':{},'media':{}}
        for name,value in source_values.items():
            content=dump(value)
            files['original-attempt/'+name+'.json']=content
            inventory['sources'][name]={'path':name+'.json','sha256':sha(content)}
        files['original-attempt/inventory.json']=dump(inventory)
        files['fixture-provenance.json']=dump({'diagnostic_fixture':True,
                                              'physical_acceptance_claimed':False,
                                              'scope':'nine-frame synthetic width protocol only'})
        for name in ('original-events.json','original-green-packet.json','site.json','acquisition.json'):
            files.pop(name,None)
        spec_path=HERE/('diagnostic-'+slug+'.json')
        spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
        reference={'source':str(spec_path.relative_to(REPO)),
                   'sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest()}
        recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',**reference}],
                'generator':reference}
        recipe_path=HERE/('diagnostic-'+slug+'-recipe.json')
        recipe_path.write_text(dump(recipe))
        relevant=[d for d in plan['requirement_dispositions'] if case_id in d['case_ids']]
        requirements=[{'disposition_index':d['disposition_index'],'requirement':d['requirement'],
                       'source':d['source'],'output_key':'alley_width_requirement_'+str(d['disposition_index']),
                       'method':'measure_alley_width','value_type':'object','kind':'measured',
                       'inputs':['original-attempt/frame_map.json','original-attempt/alley_geometry.json',
                                 'original-attempt/width_history.json']} for d in relevant]
        contract_path=HERE/('measurement-'+slug+'.json')
        contract_path.write_text(dump({'format':'worker-measurement-contract','case_id':case_id,
                                       'requirements':requirements,
                                       'negative':{'remove':['original-attempt/width_history.json'],
                                                   'error_contains':'Missing required source: original-attempt/width_history.json'}}))
        entry['fixture_recipe']=str(recipe_path.relative_to(REPO))
        entry['measurement_contract']=contract_path.name
    manifest_path.write_text(dump(manifest))
    return len(manifest['cases'])


if __name__=='__main__':print(build())
