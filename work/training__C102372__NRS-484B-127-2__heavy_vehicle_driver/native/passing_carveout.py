"""Source-bound CPU diagnostic for a truck that follows, passes, and returns."""
from __future__ import annotations
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from measure_gap import WIDTH_MIN_M, polygon, sha

NAMES=('native_samples.jsonl','following_context.json','road.xodr')


def measure(source_dir):
    root=Path(source_dir)
    manifest=json.loads((root/'source-manifest.json').read_text())
    if manifest.get('format')!='c102372-passing-source-v1' or set(manifest.get('sha256',{}))!=set(NAMES):
        raise ValueError('Incomplete passing source manifest')
    for name in NAMES:
        if not (root/name).is_file() or sha(root/name)!=manifest['sha256'][name]:
            raise ValueError('Passing source missing or changed: '+name)
    road=ET.parse(root/'road.xodr').getroot().find('road')
    if road is None or road.get('id')!='1' or float(road.get('length'))!=650 or \
            {item.get('id') for item in road.findall('lanes/laneSection/right/lane')}!={'-1'} or \
            {item.get('id') for item in road.findall('lanes/laneSection/left/lane')}!={'1'} or \
            [float(item.get('a')) for item in road.findall('elevationProfile/elevation')]!=[0,0,4,0]:
        raise ValueError('Passing source road differs')
    context=json.loads((root/'following_context.json').read_text())
    if context.get('source_kind') not in ('synthetic_cpu_fixture','native_observation') or \
            context.get('same_direction_lane_count')!=1 or \
            context.get('passing_attempt') not in (True,False) or \
            context.get('opposing_traffic_source') not in ('synthetic_empty','original_observation'):
        raise ValueError('Passing context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Full passing frame source absent')
    offsets=[];lane_ids=[];min_clearance=math.inf
    for index,row in enumerate(rows):
        if row.get('native_frame')!=index or abs(row.get('time_s',-1)-index/20)>.002:
            raise ValueError('Passing source frame/time differs')
        if row.get('opposing_lane_actors')!=[]:
            raise ValueError('Opposing-lane source is not clear')
        ego=row.get('ego',{});lead=row.get('lead',{})
        if any(actor.get('actor_class')!='truck_or_combination' or actor.get('road_id')!=1 or
               actor.get('speed_mps',0)<=0 for actor in (ego,lead)) or lead.get('lane_id')!=-1:
            raise ValueError('Passing truck source differs')
        eb=polygon(ego.get('body_xy_m'),'ego');lb=polygon(lead.get('body_xy_m'),'lead')
        if any(max(y for _,y in body)-min(y for _,y in body)<WIDTH_MIN_M for body in (eb,lb)):
            raise ValueError('Passing truck below 80-inch width')
        if any(not 0<x<650 or not -4<y<4 for body in (eb,lb) for x,y in body):
            raise ValueError('Passing truck outside source road')
        ecx=statistics.mean(x for x,_ in eb);lcx=statistics.mean(x for x,_ in lb)
        ecy=statistics.mean(y for _,y in eb);lcy=statistics.mean(y for _,y in lb)
        lane=-1 if ecy<0 else 1
        if ego.get('lane_id')!=lane or abs(lcy+2)>.01:
            raise ValueError('Passing actor lane/body differs')
        dx=max(0,abs(ecx-lcx)-12);dy=max(0,abs(ecy-lcy)-2.6)
        clearance=math.hypot(dx,dy)
        if clearance<=.1:raise ValueError('Passing truck bodies collide')
        min_clearance=min(min_clearance,clearance)
        offsets.append(ecx-lcx);lane_ids.append(lane)
    if any(lane!=-1 for lane in lane_ids[:40]+lane_ids[-40:]) or max(offsets[:40])>=-12:
        raise ValueError('Initial/final following lane or initial order differs')
    passed=(any(lane==1 for lane in lane_ids[80:400]) and
            min(offsets[:40])< -12 and min(offsets[-40:])>12 and
            any(abs(offsets[i])<12 and lane_ids[i]==1 for i in range(80,400)))
    if context['passing_attempt']!=passed:
        raise ValueError('Passing sequence differs from context')
    return {'format':'c102372-passing-diagnostic-v1','frames':480,
            'passing_sequence_observed':passed,
            'initial_center_offset_m':round(offsets[0],4),
            'final_center_offset_m':round(offsets[-1],4),
            'opposing_lane_frames':sum(lane==1 for lane in lane_ids),
            'minimum_body_clearance_m':round(min_clearance,4),
            'source_kind':context['source_kind'],
            'physical_opposing_clearance_verified':False,
            'legal_verdict_claimed':False,'sources':manifest['sha256']}
