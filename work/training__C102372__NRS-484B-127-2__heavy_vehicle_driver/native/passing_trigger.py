"""Source-bound fallback decisions for the planned passing-and-return case."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from passing_carveout import measure
from passing_engineering import ASSIGNMENT,CASE,TRIGGERS


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extract(source_dir):
    source=Path(source_dir)
    context=json.loads((source/'following_context.json').read_text())
    if context.get('case_id')!=ASSIGNMENT+'__'+CASE:
        raise ValueError('Passing source case identity differs')
    value=measure(source)
    metrics={name:value[name] for name in ('final_center_offset_m',
        'minimum_body_clearance_m','opposing_lane_frames')}
    result={'format':'c102372-passing-trigger-v1','case_id':ASSIGNMENT+'__'+CASE,
            'metrics':metrics,'metric_sha256':digest(metrics),
            'sources':value['sources'],'source_kind':value['source_kind'],
            'passing_sequence_observed':value['passing_sequence_observed'],
            'physical_opposing_clearance_verified':False}
    return result


def decide(result,candidate,diagnostic=False):
    if candidate not in TRIGGERS:raise ValueError('Unknown passing fallback')
    if result.get('format')!='c102372-passing-trigger-v1' or \
       result.get('case_id')!=ASSIGNMENT+'__'+CASE or \
       result.get('metric_sha256')!=digest(result.get('metrics')) or \
       set(result.get('sources',{}))!={'native_samples.jsonl','following_context.json','road.xodr'}:
        raise ValueError('Passing fallback metric identity or digest differs')
    if result.get('source_kind')!='native_observation' and not diagnostic:
        raise ValueError('Original Native passing source required for dispatch')
    if result.get('source_kind') not in ('native_observation','synthetic_cpu_fixture'):
        raise ValueError('Unknown passing source kind')
    if result.get('physical_opposing_clearance_verified') is not False:
        raise ValueError('Passing physical clearance claim differs')
    trigger=TRIGGERS[candidate];number=result['metrics'].get(trigger['metric'])
    if not isinstance(number,(int,float)) or isinstance(number,bool):
        raise ValueError('Passing fallback metric missing')
    return number<trigger['threshold']
