"""Tiny case-specific synthetic Native-shaped CPU fixtures, never originals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from driveway_case import CASES, SOURCE_ROLES

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def write(path,value):
    path.write_text(json.dumps(value,separators=(',',':'))+'\n',encoding='utf-8')


def site(item):
    data={'cell_id':'C213645','actor':'cycle_or_scooter_operator',
          'district_type':'residence','access_type':'driveway','vehicle_type':'bicycle',
          'map_id':'synthetic-map','sidewalk_area_id':'synthetic-sidewalk',
          'vehicle_blueprint_id':'vehicle.bh.crossbike',
          'pedestrian_blueprint_id':'walker.pedestrian.0001',
          'ego_spawn_z':1.,'pedestrian_spawn_z':1.,'pedestrian_speed_mps':1.,
          'edge_point_xy':[0,0],'edge_normal_xy':[1,0],
          'approach_route_xy':[[-5,0],[-2,0],[2,0]],
          'stop_point_xy':[-.5,0],
          'pedestrian_route_xy':[[0,-3],[0,3]],
          'pedestrian_conflict_center_xy':[0,0],
          'pedestrian_conflict_radius_m':2.,
          'requested_stop':item.stop,'requested_pedestrian':item.pedestrian,
          'requested_yield':item.yield_to_pedestrian}
    for role in SOURCE_ROLES:data[role+'_source_sha256']='synthetic-'+role
    return data


def main():
    base=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    mapping=[json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines() if line]
    distances=[5,4,3,2,1,.5,.1,-.2,-1]
    for item in CASES:
        spec=json.loads(json.dumps(base))
        for unrelated in ('alley_context.json','body_history.jsonl','speed_samples.jsonl'):
            spec['files'].pop(unrelated,None)
        packet=site(item)
        history=[]
        for i,frame in enumerate(mapping):
            history.append({'original_frame':frame['carla_frame'],'time_s':frame['time_s'],
                            'source_sha256':'synthetic-diagnostic',
                            'vehicle_motion_source_sha256':'synthetic-motion',
                            'edge_source_sha256':packet['sidewalk_edge_source_sha256'],
                            'pedestrian_motion_source_sha256':packet['pedestrian_route_source_sha256'],
                            'yield_source_sha256':packet['operator_yield_plan_source_sha256'],
                            'ego_id':'synthetic-cycle','vehicle_type':'bicycle',
                            'speed_mps':0 if item.stop and i in (3,4,5) else 2,
                            'distance_before_sidewalk_edge_m':distances[i],
                            'pedestrian_in_conflict_area':item.pedestrian and i>=5,
                            'pedestrian_actor_ids':['synthetic-pedestrian'] if item.pedestrian else [],
                            'operator_yield_observed':item.yield_to_pedestrian and i==5,
                            'pedestrian_position_xy':[0,0] if item.pedestrian else None})
        spec['files']['driveway-site.json']=json.dumps(packet)+'\n'
        spec['files']['driveway-history.jsonl']=''.join(json.dumps(row)+'\n' for row in history)
        spec['files']['diagnostic-source-note.json']=json.dumps({
            'source_kind':'synthetic_diagnostic_fixture','accepted_original_source':False,
            'case_id':ROOT.name+'__'+item.case_id})+'\n'
        output=ROOT/('diagnostic-'+item.case_id+'.json');write(output,spec)
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-input.json','source':str(output.relative_to(REPO)),
                            'sha256':digest}],
                'generator':{'source':str(output.relative_to(REPO)),'sha256':digest}}
        write(ROOT/('diagnostic-'+item.case_id+'-recipe.json'),recipe)


if __name__=='__main__':
    main()
