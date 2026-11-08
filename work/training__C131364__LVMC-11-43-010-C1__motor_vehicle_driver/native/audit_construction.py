"""Independently check the exact clause and 1,920 authored lane-use rows."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json';road=HERE/'road.xodr'
    manifest_path=HERE/'drafts'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    frozen=json.loads(assignment.read_text())
    if (frozen['law_id']!='LVMC-11-43-010-C1' or
        frozen['law_record']['text']!='The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the left lane to turn left or complete a U-turn.' or
        len(frozen['local_snapshot']['memberships']['full-train'])!=0 or
        manifest['assignment_id']!=CASE.name or
        manifest['assignment_sha256']!=sha(assignment) or
        manifest['case_plan_sha256']!=sha(plan) or
        manifest['road_sha256']!=sha(road) or
        manifest['delivery_ready'] or manifest['actual_left_exit_observed']):
        raise ValueError('C131364 frozen scope or source differs')
    xml=ET.parse(road).getroot()
    arc=xml.find('./road/planView/geometry/arc')
    lanes={int(row.attrib['id']):row.attrib['type'] for row in xml.findall('.//lane')}
    if (abs(float(arc.attrib['curvature'])-1/22)>1e-9 or
        lanes!={0:'none',-1:'driving',-2:'driving'} or
        len(xml.findall('road'))!=1):
        raise ValueError('C131364 authored two-lane ring differs')
    expected={(w,c) for w in ('witness_1','witness_2')
              for c in ('primary','fallback1','fallback2','fallback3')}
    seen=set();count=0
    for item in manifest['entries']:
        witness=item['case_id'].removeprefix(CASE.name+'__')
        candidate=item['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('C131364 candidate coverage differs')
        seen.add((witness,candidate))
        folder=HERE/'drafts'/witness/candidate
        config_path=folder/'config.json';track=folder/'requested-tracks.jsonl'
        config=json.loads(config_path.read_text())
        lane,radius=(-1,23.75) if witness=='witness_1' else (-2,27.25)
        camera='elevated_overview_plus_four' if candidate=='fallback2' else 'four_views'
        speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
        if (item['config_sha256']!=sha(config_path) or item['tracks_sha256']!=sha(track) or
            config['assignment_sha256']!=sha(assignment) or
            config['case_plan_sha256']!=sha(plan) or config['road_sha256']!=sha(road) or
            config['tracks_sha256']!=sha(track) or config['requested_lane_id']!=lane or
            config['requested_lane_radius_m']!=radius or config['camera_policy']!=camera or
            config['law_id']!='LVMC-11-43-010-C1' or config['cell_id']!='C131364' or
            config['status']!='unselected_native_request' or
            config['actual_left_exit_observed'] or config['exit_connector_verified']):
            raise ValueError('C131364 exact config differs')
        rows=[json.loads(line) for line in track.read_text().splitlines()]
        if len(rows)!=240:raise ValueError('C131364 frame coverage differs')
        for i,row in enumerate(rows):
            time_s=(i+1)/20
            travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
            theta=-math.pi/2+travel/radius
            if (row['frame']!=i or abs(row['time_s']-time_s)>1e-6 or
                row['lane_id']!=lane or row['requested_radius_m']!=radius or
                abs(row['ego_x_m']-radius*math.cos(theta))>1e-5 or
                abs(row['ego_y_m']-radius*math.sin(theta))>1e-5 or
                abs(row['ego_heading_deg']-round(math.degrees(theta+math.pi/2)%360,6))>1e-6 or
                row['ego_speed_mps']!=(0 if candidate=='fallback3' and speed*time_s>12 else speed) or
                row['intended_exit_kind']!='left_turn' or row['actual_exit_observed'] or
                row['roundabout_verified']):
                raise ValueError(f'C131364 request differs at {i}')
            count+=1
    if seen!=expected or count!=1920:raise ValueError('C131364 request set incomplete')
    result={'format':'c131364-independent-construction-audit-v1',
        'manifest_sha256':sha(manifest_path),'requests_checked':8,
        'requested_rows_checked':count,'actual_left_exit_observed':False,
        'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
