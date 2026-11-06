"""Independent source/cell and simultaneous reverse-intersection audit."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    source=ROOT/'inputs'/HERE.name/'assignment.json'
    a=json.loads(source.read_text())
    if a['law_record']['text']!='The driver of a vehicle: Shall not back into an intersection, on or over a crosswalk, or around a street corner.':
        raise ValueError('Frozen law differs')
    if (a['cell']['layout'],a['cell']['maneuver'],a['cell']['control'])!=('intersection','reverse','intersection_boundary'):
        raise ValueError('Frozen cell differs')
    road=ET.fromstring((HERE/'native/road.xodr').read_text())
    if len(road.findall('junction/connection'))!=2 or road.findall(".//object[@type='crosswalk']"):
        raise ValueError('Authored unmarked intersection differs')
    findings={}
    for suffix in ('condition_a','condition_b'):
        path=HERE/'fixtures'/suffix/'native_samples.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        if len(rows)!=480:raise ValueError('Saved sample count differs')
        events=[]
        for i,row in enumerate(rows):
            if row['native_frame']!=2000+i or row['video_frame']!=i or abs(row['time_s']-i/20)>1e-8:
                raise ValueError('Independent frame/time join differs')
            if row['signed_forward_velocity_m_s']<-.05:
                xs=[p[0] for p in row['body_xy_m']]
                ys=[p[1] for p in row['body_xy_m']]
                width=max(0,min(max(xs),7)-max(min(xs),-7))
                height=max(0,min(max(ys),7)-max(min(ys),-7))
                if width*height>0:events.append((i,width*height))
        if (suffix=='condition_a' and events) or (suffix=='condition_b' and not events):
            raise ValueError('Independent backing-intersection contrast differs')
        findings[suffix]={'event_frames':len(events),'max_overlap_m2':max([v for _,v in events],default=0),
                          'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    print(json.dumps({'passed':True,'scope':'independent synthetic C110763 pair audit',
                      'assignment_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                      'comparison_variable':'reverse_path_intersection_occupancy',
                      'cases':findings,'ready':False},indent=2))


if __name__=='__main__':main()
