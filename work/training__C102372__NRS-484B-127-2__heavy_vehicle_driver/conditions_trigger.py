"""Source-bound fallback decisions for the controlled conditions pair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from conditions_engineering import ASSIGNMENT,CASES,TRIGGERS
from conditions_qualifier import measure


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extract(source_dir,case):
    if case not in CASES:raise ValueError('Unknown conditions case')
    root=Path(source_dir)
    context=json.loads((root/'following_context.json').read_text())
    if context.get('case_id')!=ASSIGNMENT+'__'+case or \
       context.get('event')!=('steady' if case=='conditions_steady' else
                              'lead_brake_with_obstacle'):
        raise ValueError('Conditions trigger case/context differs')
    value=measure(root)
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    speed=max(abs(row['ego']['speed_mps']-row['lead']['speed_mps']) for row in rows)
    clearances=[]
    for row in rows:
        obstacle=row.get('obstacle')
        if obstacle is not None:
            clearances.append(min(x for x,_ in obstacle['body_xy_m'])-
                              max(x for x,_ in row['lead']['body_xy_m']))
    metrics={'minimum_surface_gap_m':value['minimum_surface_gap_m'],
             'surface_gap_compression_m':value['surface_gap_compression_m'],
             'maximum_speed_difference_mps':round(speed,4),
             'minimum_lead_obstacle_clearance_m':round(min(clearances),4)
                    if clearances else None}
    return {'format':'c102372-conditions-trigger-v1',
            'case_id':ASSIGNMENT+'__'+case,'metrics':metrics,
            'metric_sha256':digest(metrics),'sources':value['sources'],
            'source_kind':value['source_kind'],
            'lead_braking_gap_compression_observed':value[
                'lead_braking_gap_compression_observed'],
            'physical_conditions_permit_verified':False}


def decide(result,case,candidate,diagnostic=False):
    if case not in CASES or candidate not in TRIGGERS[case]:
        raise ValueError('Unknown conditions fallback')
    if result.get('format')!='c102372-conditions-trigger-v1' or \
       result.get('case_id')!=ASSIGNMENT+'__'+case or \
       result.get('metric_sha256')!=digest(result.get('metrics')) or \
       set(result.get('sources',{}))!={'native_samples.jsonl','following_context.json','road.xodr'} or \
       result.get('physical_conditions_permit_verified') is not False:
        raise ValueError('Conditions fallback metric identity or digest differs')
    if result.get('source_kind')!='native_observation' and not diagnostic:
        raise ValueError('Original Native conditions source required for dispatch')
    if result.get('source_kind') not in ('native_observation','synthetic_cpu_fixture'):
        raise ValueError('Unknown conditions source kind')
    target=case=='conditions_lead_brake'
    if result.get('lead_braking_gap_compression_observed') is not target:
        raise ValueError('Conditions event observation differs from case')
    trigger=TRIGGERS[case][candidate];number=result['metrics'].get(trigger['metric'])
    if not isinstance(number,(int,float)) or isinstance(number,bool):
        raise ValueError('Conditions fallback metric missing')
    return number<trigger['threshold'] if trigger['op']=='<' else number>trigger['threshold']
