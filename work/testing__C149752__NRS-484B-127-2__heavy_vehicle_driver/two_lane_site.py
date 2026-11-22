"""Authored two-lane one-way exception site; Native availability unverified."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROAD=Path(__file__).resolve().parent/'native-map-plan/two-lane-truck-road.xodr'


def validate_site():
    document=ET.parse(ROAD).getroot()
    roads=document.findall('road')
    if document.tag!='OpenDRIVE' or len(roads)!=1:raise ValueError('Wrong two-lane road document')
    road=roads[0]
    if road.get('id')!='149238' or float(road.get('length','0'))!=1200:
        raise ValueError('Wrong two-lane road identity or length')
    geometry=road.find('planView/geometry')
    if geometry is None or geometry.find('line') is None or any(
            float(geometry.get(k,'nan'))!=v for k,v in
            {'s':0,'x':0,'y':0,'hdg':0,'length':1200}.items()):
        raise ValueError('Two-lane road is not the authored straight approach')
    sections=road.findall('lanes/laneSection')
    if len(sections)!=1 or float(sections[0].get('s','nan'))!=0:
        raise ValueError('Unexpected two-lane sections')
    driving=sections[0].findall('right/lane[@type="driving"]')
    if {int(lane.get('id')) for lane in driving}!={-1,-2} or len(driving)!=2:
        raise ValueError('Two forward driving lanes required')
    for lane in driving:
        width=lane.find('width')
        if width is None or any(float(width.get(k,'nan'))!=v for k,v in
                {'sOffset':0,'a':3.8,'b':0,'c':0,'d':0}.items()):
            raise ValueError('Two-lane width differs')
    return {'road_source':str(ROAD),'road_sha256':hashlib.sha256(ROAD.read_bytes()).hexdigest(),
            'road_id':149238,'following_lane_id':-1,
            'available_same_direction_lanes':[-1,-2],
            'same_direction_lane_count':2,'lane_width_m':3.8}
