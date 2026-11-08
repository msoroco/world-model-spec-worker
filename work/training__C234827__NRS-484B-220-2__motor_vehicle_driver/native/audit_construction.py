"""Independent road, source and 1,920-row rotary request audit."""
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
    plan=CASE/'case-plan.json'
    road=HERE/'road.xodr'
    island=HERE/'island-geometry.json'
    manifest_path=HERE/'drafts'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    sources={'assignment_sha256':assignment,'case_plan_sha256':plan,
             'road_sha256':road,'island_geometry_sha256':island}
    if (manifest['format']!='c234827-native-construction-manifest-v1' or
            manifest['assignment_id']!=CASE.name or
            any(manifest[key]!=sha(value) for key,value in sources.items()) or
            manifest['original_native_observed'] or manifest['physical_island_verified'] or
            manifest['delivery_ready']):
        raise ValueError('Rotary source provenance differs')
    source=json.loads(assignment.read_text())
    case_plan=json.loads(plan.read_text())
    if (source['law_record']['text']!=
            'A vehicle passing around a rotary traffic island shall be driven only to the right of such island.' or
            source['law_id']!='NRS-484B-220-2' or
            {item['case_id'] for item in case_plan['cases']}!=
            {CASE.name+'__reference',CASE.name+'__contrast'} or
            case_plan['existing_evidence'][0]['status']!='unreviewed_membership_only'):
        raise ValueError('Rotary frozen scope or accepted-membership limit differs')
    geometry=json.loads(island.read_text())
    if (geometry['center_xy_m']!=[0,0] or
            geometry['requested_island_radius_m']!=15 or
            geometry['reference_centerline_radius_m']!=22 or
            geometry['inner_lane_center_radius_m']!=23.75 or
            geometry['outer_lane_center_radius_m']!=27.25 or
            geometry['physical_island_verified']):
        raise ValueError('Authored island geometry differs')
    xml=ET.parse(road).getroot()
    road_element=xml.find('road')
    arc=road_element.find('./planView/geometry/arc')
    lanes={int(item.attrib['id']):item.attrib['type'] for item in xml.findall('.//lane')}
    if (abs(float(road_element.attrib['length'])-2*math.pi*22)>1e-6 or
            abs(float(arc.attrib['curvature'])-1/22)>1e-9 or
            lanes!={0:'none',-1:'driving',-2:'driving'} or
            xml.findall('.//signal')):
        raise ValueError('Authored rotary road differs')
    expected={(case,candidate) for case in ('reference','contrast')
              for candidate in ('primary','fallback1','fallback2','fallback3')}
    seen=set();count=0
    for item in manifest['entries']:
        case=item['case_id'].removeprefix(CASE.name+'__')
        candidate=item['candidate_id']
        if ((case,candidate) not in expected or (case,candidate) in seen or
                item['status']!='unselected_native_request'):
            raise ValueError('Rotary candidate coverage differs')
        seen.add((case,candidate))
        folder=HERE/'drafts'/case/candidate
        config_path=folder/'config.json';track=folder/'requested-tracks.jsonl'
        config=json.loads(config_path.read_text())
        if (item['config_sha256']!=sha(config_path) or
                item['tracks_sha256']!=sha(track) or
                any(config.get(key)!=sha(value) for key,value in sources.items()) or
                config['tracks_sha256']!=sha(track) or
                config['case_id']!=item['case_id'] or
                config['candidate_id']!=candidate or
                config['island_side_request']!=case or
                config['status']!='unselected_native_request' or
                config['physical_island_verified']):
            raise ValueError('Rotary config/source join differs')
        rows=[json.loads(line) for line in track.read_text().splitlines()]
        if len(rows)!=240:raise ValueError('Rotary request count differs')
        direction=1 if case=='reference' else -1
        start=-math.pi/2 if case=='reference' else math.pi/2
        radius=27.25 if candidate=='fallback2' else 23.75
        lane=-2 if candidate=='fallback2' else -1
        speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
        for i,row in enumerate(rows):
            t=(i+1)/20
            distance=min(12,speed*t) if candidate=='fallback3' else speed*t
            theta=start+direction*distance/radius
            heading=(math.degrees(theta+direction*math.pi/2)%360)
            if (row['frame']!=i or abs(row['time_s']-t)>1e-6 or
                    row['source_kind']!='authored_native_request' or
                    row['case']!=case or row['candidate_id']!=candidate or
                    row['lane_id']!=lane or row['requested_radius_m']!=radius or
                    row['island_center_xy_m']!=[0,0] or
                    abs(row['ego_x_m']-radius*math.cos(theta))>1e-5 or
                    abs(row['ego_y_m']-radius*math.sin(theta))>1e-5 or
                    abs(row['ego_heading_deg']-round(heading,6))>1e-6 or
                    row['ego_speed_mps']!=(0 if candidate=='fallback3' and speed*t>12 else speed) or
                    row['physical_island_verified']):
                raise ValueError('Rotary requested track differs')
            count+=1
    if seen!=expected or count!=1920:
        raise ValueError('Rotary construction coverage incomplete')
    result={'format':'c234827-independent-construction-audit-v1',
            'manifest_sha256':sha(manifest_path),'requests_checked':8,
            'requested_rows_checked':count,
            'existing_accepted_memberships_replayed':0,
            'physical_island_verified':False,'delivery_ready':False}
    (HERE/'construction-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
