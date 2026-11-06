"""Independent frozen-cell, law and saved corner contrast audit."""
import hashlib,json,math
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LAW='The driver of a vehicle: Shall not back into an intersection, on or over a crosswalk, or around a street corner.'
def area(vertices):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(vertices,vertices[1:]+vertices[:1])))/2
def main():
    source=ROOT/'inputs'/HERE.name/'assignment.json'
    assignment=json.loads(source.read_text())
    if assignment['law_record']['text']!=LAW or (assignment['cell']['layout'],assignment['cell']['maneuver'],assignment['cell']['control'])!=('intersection','reverse','street_corner'):
        raise ValueError('Frozen law/cell differs')
    root=ET.fromstring((HERE/'native/road.xodr').read_text())
    if len(root.findall('junction/connection'))!=2 or len(root.findall(".//object[@type='crosswalk']"))!=1:
        raise ValueError('Authored junction/crosswalk context differs')
    observations={}
    for suffix in ('condition_a','condition_b'):
        path=HERE/'fixtures'/suffix/'native_samples.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        if len(rows)!=480:raise ValueError('Saved cardinality differs')
        turning=0;max_heading=0;crosswalk=0;travel=0
        for index,row in enumerate(rows):
            if row['native_frame']!=3000+index or row['video_frame']!=index or abs(row['time_s']-index/20)>1e-8:
                raise ValueError('Independent frame/time join differs')
            if abs(area(row['body_xy_m'])-11.44)>.001:raise ValueError('Independent body geometry differs')
            if index:
                travel+=math.dist(row['native_center_xy_m'],rows[index-1]['native_center_xy_m'])
            if row['signed_forward_velocity_m_s']<-.05:
                max_heading=max(max_heading,abs(row['heading_deg']))
                if index and abs(row['heading_deg']-rows[index-1]['heading_deg'])>.1:turning+=1
                if min(v[0] for v in row['body_xy_m']) < -15:crosswalk+=1
        if crosswalk or (suffix=='condition_a' and (turning or max_heading)) or (suffix=='condition_b' and (turning<100 or abs(max_heading-90)>.001)):
            raise ValueError('Independent corner contrast differs')
        observations[suffix]={'reverse_turning_frames':turning,'max_heading_change_deg':max_heading,
                              'reverse_distance_m':round(travel,5),
                              'saved_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if abs(observations['condition_a']['reverse_distance_m']-
           observations['condition_b']['reverse_distance_m'])>.002:
        raise ValueError('Controlled pair reverse distance differs')
    print(json.dumps({'passed':True,'assignment_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                      'scope':'independent authored/synthetic corner audit; no Native run',
                      'comparison_variable':'backing_around_street_corner','cases':observations,'ready':False},indent=2))
if __name__=='__main__':main()
