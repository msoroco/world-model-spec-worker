"""Build a synthetic same-direction road and sign source-shaped CPU fixture."""

from copy import deepcopy
import json
from pathlib import Path


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__posted_one_way'


def build(left):
    result=deepcopy(left);files=result['files']
    previous=[json.loads(line) for line in files.pop('directed_roadway_footprints.jsonl').splitlines() if line]
    if not previous:
        raise ValueError('One-way diagnostic needs original road-shaped rows')
    road=[];sign=[]
    for row in previous:
        road.append({'frame':row['frame'],'time_s':row['time_s'],
            'ego_id':row['ego_id'],'ego_corners':row['ego_corners'],
            'roadway_center_point_xy':row['roadway_center_point_xy'],
            'travel_tangent_xy':row['travel_tangent_xy'],
            'left_lane_tangent_xy':[1.0,0.0],
            'left_road_edge_xy':row['left_road_edge_xy'],
            'right_road_edge_xy':row['right_road_edge_xy'],
            'road_id':row['subject_road_id'],'right_lane_id':-1,'left_lane_id':-2,
            'right_lane_width_m':3.5,'left_lane_width_m':3.5})
        sign.append({'frame':row['frame'],'time_s':row['time_s'],
            'actor_id':'fixture-one-way-sign-401','blueprint_id':'static.prop.oneway',
            'position_m':[105.0,4.0,0.1],
            'designation_verified':False,'posting_authority_verified':False})
    files['one_way_roadway.jsonl']=''.join(json.dumps(row)+'\n' for row in road)
    files['one_way_sign.jsonl']=''.join(json.dumps(row)+'\n' for row in sign)
    manifest=json.loads(files['capture/manifest.json']);manifest['case_id']=CASE
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['one-way-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note',
        'use':'synthetic same-direction two-lane geometry and sign actor for CPU saved processing only',
        'designation_verified':False,'posting_authority_verified':False,
        'physical_acceptance_claimed':False,'builder':'one_way_diagnostic_builder.py'},indent=2)+'\n'
    return result


def main():
    root=Path(__file__).parent;output=root/'one-way-diagnostic.json'
    if output.exists():
        raise ValueError('Retain prior one-way diagnostic')
    output.write_text(json.dumps(build(json.loads((root/'left-diagnostic.json').read_text())),
                                 allow_nan=False)+'\n')


if __name__=='__main__':
    main()
