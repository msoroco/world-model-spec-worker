"""Independently audit roundabout source, geometry and 1,920 requests."""
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
    island=HERE/'island-geometry.json';manifest_path=HERE/'drafts'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    sources={'assignment_sha256':assignment,'case_plan_sha256':plan,
             'road_sha256':road,'island_geometry_sha256':island}
    if (manifest.get('format')!='c234827-lvmc-construction-manifest-v1' or
            manifest.get('assignment_id')!=CASE.name or
            any(manifest.get(key)!=sha(path) for key,path in sources.items()) or
            manifest['original_native_observed'] or manifest['roundabout_verified'] or
            manifest['delivery_ready']):
        raise ValueError('Roundabout construction source differs')
    frozen=json.loads(assignment.read_text())
    case_plan=json.loads(plan.read_text())
    if (frozen['law_id']!='LVMC-11-43-010-A' or
            frozen['law_record']['text']!=
            'The following regulations pertain to the operation of vehicles within a roundabout: All vehicular travel shall be in a counterclockwise direction.' or
            {row['case_id'] for row in case_plan['cases']}!=
            {CASE.name+'__witness_1',CASE.name+'__witness_2'} or
            len(frozen['local_snapshot']['memberships']['full-train'])!=3):
        raise ValueError('Frozen roundabout statute or membership scope differs')
    geometry=json.loads(island.read_text())
    if (geometry['center_xy_m']!=[0,0] or
            geometry['requested_island_radius_m']!=15 or
            geometry['reference_centerline_radius_m']!=22 or
            geometry['inner_lane_center_radius_m']!=23.75 or
            geometry['outer_lane_center_radius_m']!=27.25 or
            geometry['physical_island_verified']):
        raise ValueError('Authored roundabout island geometry differs')
    xml=ET.parse(road).getroot();road_element=xml.find('road')
    arc=road_element.find('./planView/geometry/arc')
    lanes={int(row.attrib['id']):row.attrib['type'] for row in xml.findall('.//lane')}
    if (abs(float(road_element.attrib['length'])-2*math.pi*22)>1e-6 or
            abs(float(arc.attrib['curvature'])-1/22)>1e-9 or
            lanes!={0:'none',-1:'driving',-2:'driving'} or
            xml.findall('.//signal')):
        raise ValueError('Authored roundabout road differs')
    expected={(w,c) for w in ('witness_1','witness_2')
              for c in ('primary','fallback1','fallback2','fallback3')}
    seen=set();count=0
    for item in manifest['entries']:
        witness=item['case_id'].removeprefix(CASE.name+'__')
        candidate=item['candidate_id']
        if ((witness,candidate) not in expected or (witness,candidate) in seen or
                item['status']!='unselected_native_request'):
            raise ValueError('Roundabout candidate coverage differs')
        seen.add((witness,candidate))
        folder=HERE/'drafts'/witness/candidate
        config_path=folder/'config.json';track=folder/'requested-tracks.jsonl'
        config=json.loads(config_path.read_text())
        if (item['config_sha256']!=sha(config_path) or
                item['tracks_sha256']!=sha(track) or
                any(config.get(key)!=sha(path) for key,path in sources.items()) or
                config['tracks_sha256']!=sha(track) or
                config['case_id']!=item['case_id'] or
                config['direction_request']!=witness or
                config['candidate_id']!=candidate or
                config['law_id']!='LVMC-11-43-010-A' or
                config['status']!='unselected_native_request' or
                config['roundabout_verified']):
            raise ValueError('Roundabout config or source join differs')
        rows=[json.loads(line) for line in track.read_text().splitlines()]
        if len(rows)!=240:raise ValueError('Roundabout request count differs')
        direction=1 if witness=='witness_1' else -1
        start=-math.pi/2 if direction==1 else math.pi/2
        radius=27.25 if candidate=='fallback2' else 23.75
        lane=-2 if candidate=='fallback2' else -1
        speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
        for i,row in enumerate(rows):
            time_s=(i+1)/20
            travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
            theta=start+direction*travel/radius
            heading=math.degrees(theta+direction*math.pi/2)%360
            if (row['frame']!=i or abs(row['time_s']-time_s)>1e-6 or
                    row['source_kind']!='authored_native_request' or
                    row['witness']!=witness or row['candidate_id']!=candidate or
                    row['lane_id']!=lane or row['requested_radius_m']!=radius or
                    row['island_center_xy_m']!=[0,0] or
                    abs(row['ego_x_m']-radius*math.cos(theta))>1e-5 or
                    abs(row['ego_y_m']-radius*math.sin(theta))>1e-5 or
                    abs(row['ego_heading_deg']-round(heading,6))>1e-6 or
                    row['ego_speed_mps']!=(0 if candidate=='fallback3' and speed*time_s>12 else speed) or
                    row['roundabout_verified']):
                raise ValueError('Roundabout requested track differs')
            count+=1
    if seen!=expected or count!=1920:
        raise ValueError('Roundabout candidate rows incomplete')
    result={'format':'c234827-lvmc-independent-construction-audit-v1',
        'manifest_sha256':sha(manifest_path),'requests_checked':8,
        'requested_rows_checked':count,'accepted_memberships_replayed':0,
        'roundabout_verified':False,'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
