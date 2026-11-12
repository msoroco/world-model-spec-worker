"""Build a synthetic three-lane source fixture for CPU saved processing."""

from copy import deepcopy
import json
from pathlib import Path


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__three_lane'


def build(left):
    result=deepcopy(left);files=result['files']
    previous=[json.loads(line) for line in files.pop('directed_roadway_footprints.jsonl').splitlines() if line]
    if not previous:raise ValueError('Three-lane diagnostic source missing')
    rows=[]
    for row in previous:
        if row['travel_tangent_xy']!=[1.0,0.0]:
            raise ValueError('Three-lane diagnostic expects eastbound source')
        rows.append({'frame':row['frame'],'time_s':row['time_s'],
            'ego_id':row['ego_id'],'ego_corners':row['ego_corners'],
            'roadway_center_point_xy':[0.0,0.0],
            'travel_tangent_xy':[1.0,0.0],
            'center_lane_tangent_xy':[1.0,0.0],
            'far_left_lane_tangent_xy':[-1.0,0.0],
            'left_road_edge_xy':[0.0,-5.25],
            'right_road_edge_xy':[0.0,5.25],
            'road_id':row['subject_road_id'],
            'right_lane_id':-1,'center_lane_id':-2,'far_left_lane_id':1,
            'lane_widths_m':[3.5,3.5,3.5],
            'applicable_lane_rule_verified':False})
    files['three_lane_roadway.jsonl']=''.join(json.dumps(row)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json']);manifest['case_id']=CASE
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['three-lane-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note',
        'use':'synthetic three-traffic-lane topology for CPU saved processing only',
        'applicable_lane_rule_verified':False,'physical_acceptance_claimed':False,
        'builder':'three_lane_diagnostic_builder.py'},indent=2)+'\n'
    return result


def main():
    root=Path(__file__).parent;output=root/'three-lane-diagnostic.json'
    if output.exists():raise ValueError('Retain prior three-lane diagnostic')
    output.write_text(json.dumps(build(json.loads((root/'left-diagnostic.json').read_text())),
                                 allow_nan=False)+'\n')


if __name__=='__main__':main()
