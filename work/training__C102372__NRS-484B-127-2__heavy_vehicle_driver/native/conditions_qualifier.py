"""Measure a saved lead-braking/gap-compression event without legal inference."""
from __future__ import annotations
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
from measure_gap import WIDTH_MIN_M, GAP_LIMIT_M, polygon, road_distance, sha

NAMES=('native_samples.jsonl','following_context.json','road.xodr')


def measure(source_dir):
    root=Path(source_dir)
    manifest=json.loads((root/'source-manifest.json').read_text())
    if manifest.get('format')!='c102372-conditions-source-v1' or set(manifest.get('sha256',{}))!=set(NAMES):
        raise ValueError('Incomplete conditions source manifest')
    for name in NAMES:
        if not (root/name).is_file() or sha(root/name)!=manifest['sha256'][name]:
            raise ValueError('Conditions source missing or changed: '+name)
    road=ET.parse(root/'road.xodr').getroot().find('road')
    if road is None or road.get('id')!='1' or float(road.get('length'))!=650 or \
            {item.get('id') for item in road.findall('lanes/laneSection/right/lane')}!={'-1'} or \
            {item.get('id') for item in road.findall('lanes/laneSection/left/lane')}!={'1'} or \
            [float(item.get('a')) for item in road.findall('elevationProfile/elevation')]!=[0,0,4,0]:
        raise ValueError('Conditions source road differs')
    profile=road.findall('elevationProfile/elevation')
    context=json.loads((root/'following_context.json').read_text())
    if context.get('source_kind') not in ('synthetic_cpu_fixture','native_observation') or \
            context.get('same_direction_lane_count')!=1 or \
            context.get('event') not in ('steady','lead_brake_with_obstacle'):
        raise ValueError('Conditions context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Full conditions frame source absent')
    gaps=[];surface_gaps=[];lead_speeds=[];ego_speeds=[];obstacle_frames=0
    for index,row in enumerate(rows):
        if row.get('native_frame')!=index or abs(row.get('time_s',-1)-index/20)>.002:
            raise ValueError('Conditions frame/time differs')
        ego=row.get('ego',{});lead=row.get('lead',{})
        if any(actor.get('actor_class')!='truck_or_combination' or actor.get('road_id')!=1 or
               actor.get('lane_id')!=-1 for actor in (ego,lead)):
            raise ValueError('Qualifying conditions truck differs')
        eb=polygon(ego.get('body_xy_m'),'ego');lb=polygon(lead.get('body_xy_m'),'lead')
        if any(max(y for _,y in body)-min(y for _,y in body)<WIDTH_MIN_M or
               any(not 0<x<650 or not -4<y<0 for x,y in body) for body in (eb,lb)):
            raise ValueError('Conditions truck width or lane differs')
        gap=min(x for x,_ in lb)-max(x for x,_ in eb)
        if gap<=0:raise ValueError('Conditions truck collision or order differs')
        gaps.append(gap)
        surface_gaps.append(road_distance(max(x for x,_ in eb),min(x for x,_ in lb),profile))
        lead_speeds.append(float(lead.get('speed_mps',-1)))
        ego_speeds.append(float(ego.get('speed_mps',-1)))
        if not 0<=lead_speeds[-1]<=20 or not 0<=ego_speeds[-1]<=20:
            raise ValueError('Conditions speed differs')
        obstacle=row.get('obstacle')
        if obstacle is not None:
            if obstacle.get('actor_class')!='stopped_vehicle' or obstacle.get('lane_id')!=-1:
                raise ValueError('Conditions obstacle class or lane differs')
            body=polygon(obstacle.get('body_xy_m'),'obstacle')
            if min(x for x,_ in body)-max(x for x,_ in lb)<=0:
                raise ValueError('Conditions lead/obstacle collision')
            obstacle_frames+=1
    lead_drop=lead_speeds[160]-lead_speeds[200]
    ego_drop=ego_speeds[180]-ego_speeds[260]
    compression=surface_gaps[0]-min(surface_gaps)
    event=obstacle_frames==480 and lead_drop>=7.9 and ego_drop>=7.9 and \
          min(surface_gaps)<GAP_LIMIT_M-.1 and surface_gaps[0]>GAP_LIMIT_M+.1 and \
          all(abs(speed-8)<.01 for speed in lead_speeds[:160]+ego_speeds[:180])
    if (context['event']=='lead_brake_with_obstacle')!=event:
        raise ValueError('Conditions event differs from measured source')
    if context['event']=='steady' and (obstacle_frames or min(surface_gaps)<GAP_LIMIT_M+.1):
        raise ValueError('Steady conditions source differs')
    return {'format':'c102372-conditions-diagnostic-v1','frames':480,
            'lead_braking_gap_compression_observed':event,
            'initial_horizontal_gap_m':round(gaps[0],4),
            'minimum_horizontal_gap_m':round(min(gaps),4),
            'initial_surface_gap_m':round(surface_gaps[0],4),
            'minimum_surface_gap_m':round(min(surface_gaps),4),
            'surface_gap_compression_m':round(compression,4),
            'lead_speed_drop_mps':round(lead_drop,4),
            'ego_speed_drop_mps':round(ego_drop,4),
            'obstacle_source_frames':obstacle_frames,
            'source_kind':context['source_kind'],
            'physical_conditions_permit_verified':False,
            'legal_verdict_claimed':False,'sources':manifest['sha256']}
