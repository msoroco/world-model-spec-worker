"""Same-cell two-direction-lane exception geometry and saved CPU diagnostic."""
from __future__ import annotations
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from geometry import open_drive
from measure_gap import WIDTH_MIN_M,sha,polygon,road_distance


def two_lane_open_drive():
    root=ET.fromstring(open_drive())
    road=root.find('road');road.set('name','C102372_follow_two_same_direction_lanes')
    right=road.find('lanes/laneSection/right')
    lane=ET.SubElement(right,'lane',id='-2',type='driving',level='false')
    ET.SubElement(lane,'width',sOffset='0',a='4.0',b='0',c='0',d='0')
    ET.SubElement(lane,'roadMark',sOffset='0',type='broken',color='white',width='0.12')
    return ET.tostring(root,encoding='unicode')


def geometry_check():
    root=ET.fromstring(two_lane_open_drive());road=root.find('road')
    right=road.findall('lanes/laneSection/right/lane')
    left=road.findall('lanes/laneSection/left/lane')
    elevations=road.findall('elevationProfile/elevation')
    if {item.get('id') for item in right}!={'-1','-2'} or \
            {item.get('id') for item in left}!={'1'} or \
            [float(item.get('a')) for item in elevations]!=[0,0,4,0]:
        raise ValueError('Two-lane hill-crest geometry differs')
    return {'passed':True,'same_direction_lane_ids':[-1,-2],
            'opposing_lane_ids':[1],'crest_height_m':4.0,
            'physical_highway_status_verified':False}


def measure(root):
    root=Path(root)
    manifest=json.loads((root/'source-manifest.json').read_text())
    names=('native_samples.jsonl','following_context.json','road.xodr')
    if manifest.get('format')!='c102372-truck-follow-source-v1' or set(
            manifest.get('sha256',{}))!=set(names):
        raise ValueError('Incomplete two-lane source manifest')
    for name in names:
        if not (root/name).is_file() or sha(root/name)!=manifest['sha256'][name]:
            raise ValueError('Two-lane source missing or changed: '+name)
    road=ET.parse(root/'road.xodr').getroot().find('road')
    lanes=road.findall('lanes/laneSection/right/lane')
    opposing=road.findall('lanes/laneSection/left/lane')
    profile=road.findall('elevationProfile/elevation')
    if {item.get('id') for item in lanes}!={'-1','-2'} or \
            len(opposing)!=1 or opposing[0].get('id')!='1' or \
            [float(item.get('s')) for item in profile]!=[0,100,150,200] or \
            [float(item.get('a')) for item in profile]!=[0,0,4,0]:
        raise ValueError('Two same-direction lanes absent from source map')
    if any(item.get('type')!='driving' or len(item.findall('width'))!=1 or
           float(item.find('width').get('a'))!=4 for item in lanes):
        raise ValueError('Two same-direction lane widths differ')
    context=json.loads((root/'following_context.json').read_text())
    if context.get('source_kind') not in ('synthetic_cpu_fixture','native_observation') or \
            context.get('same_direction_lane_count')!=2 or context.get('road_id')!=1 or \
            context.get('lane_id')!=-1 or context.get('overtaking') is not False:
        raise ValueError('Two-lane source context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Full two-lane frame source absent')
    gaps=[];surface_gaps=[]
    for index,row in enumerate(rows):
        if row.get('native_frame')!=index or abs(row.get('time_s',-1)-index/20)>.002:
            raise ValueError('Two-lane source frame/time differs')
        ego=row.get('ego',{});lead=row.get('lead',{})
        if any(actor.get('actor_class')!='truck_or_combination' or actor.get('road_id')!=1
               or actor.get('lane_id')!=-1 or actor.get('speed_mps',0)<=0
               for actor in (ego,lead)):
            raise ValueError('Qualifying truck source differs')
        e=polygon(ego.get('body_xy_m'),'ego');l=polygon(lead.get('body_xy_m'),'lead')
        if any(max(y for _,y in body)-min(y for _,y in body)<WIDTH_MIN_M for body in (e,l)):
            raise ValueError('80-inch truck width absent')
        if any(not 0 < x < 650 or not -4 < y < 0 for body in (e,l) for x,y in body):
            raise ValueError('Truck body outside source lane or road')
        gap=min(x for x,_ in l)-max(x for x,_ in e)
        if gap<=0:raise ValueError('Lead truck body order differs')
        gaps.append(gap)
        surface_gaps.append(road_distance(max(x for x,_ in e),min(x for x,_ in l),profile))
    relation='below' if max(surface_gaps)<500*.3048-.1 else 'boundary_unresolved'
    return {'format':'c102372-two-lane-exception-diagnostic-v1',
        'frames':480,'same_direction_lane_count':2,
        'minimum_horizontal_body_gap_m':round(min(gaps),5),
        'min_surface_gap_m':round(min(surface_gaps),6),
        'max_surface_gap_m':round(max(surface_gaps),6),
        'relation_to_500ft':relation,
        'below_500ft_gap_observed':max(surface_gaps)<500*.3048,
        'source_kind':context.get('source_kind'),
        'physical_lane_availability_verified':False,
        'physical_highway_status_verified':False,'legal_verdict_claimed':False,
        'sources':manifest['sha256']}
