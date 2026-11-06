"""Exact source-bound decisions for a truck that remains in its lane."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import statistics
from passing_carveout import measure
from passing_hold_engineering import ASSIGNMENT,CASE,TRIGGERS


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extract(source_dir):
    root=Path(source_dir)
    context=json.loads((root/'following_context.json').read_text())
    if context.get('case_id')!=ASSIGNMENT+'__'+CASE or context.get('passing_attempt') is not False:
        raise ValueError('Hold source case identity differs')
    value=measure(root)
    if value['passing_sequence_observed'] or value['opposing_lane_frames']:
        raise ValueError('Hold source contains passing behavior')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    metrics={'minimum_body_clearance_m':value['minimum_body_clearance_m'],
             'maximum_speed_difference_mps':round(max(abs(row['ego']['speed_mps']-
                   row['lead']['speed_mps']) for row in rows),4),
             'maximum_lane_center_error_m':round(max(abs(statistics.mean(y for _,y in
                   row['ego']['body_xy_m'])+2.) for row in rows),4)}
    return {'format':'c102372-passing-hold-trigger-v1',
            'case_id':ASSIGNMENT+'__'+CASE,'metrics':metrics,
            'metric_sha256':digest(metrics),'sources':value['sources'],
            'source_kind':value['source_kind'],'passing_sequence_observed':False,
            'physical_verification_claimed':False}


def decide(result,candidate,diagnostic=False):
    if candidate not in TRIGGERS:raise ValueError('Unknown hold fallback')
    if result.get('format')!='c102372-passing-hold-trigger-v1' or \
       result.get('case_id')!=ASSIGNMENT+'__'+CASE or \
       result.get('metric_sha256')!=digest(result.get('metrics')) or \
       set(result.get('sources',{}))!={'native_samples.jsonl','following_context.json','road.xodr'} or \
       result.get('passing_sequence_observed') is not False or \
       result.get('physical_verification_claimed') is not False:
        raise ValueError('Hold fallback metric identity or digest differs')
    if result.get('source_kind')!='native_observation' and not diagnostic:
        raise ValueError('Original Native hold source required for dispatch')
    if result.get('source_kind') not in ('native_observation','synthetic_cpu_fixture'):
        raise ValueError('Unknown hold source kind')
    trigger=TRIGGERS[candidate];number=result['metrics'].get(trigger['metric'])
    if not isinstance(number,(int,float)) or isinstance(number,bool):
        raise ValueError('Hold fallback metric missing')
    return number<trigger['threshold'] if trigger['op']=='<' else number>trigger['threshold']
