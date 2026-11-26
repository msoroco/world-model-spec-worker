"""Saved-only driveway sidewalk source and motion analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from driveway_case import CASES, measure_original, validate_case

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root,name):
    path=Path(root)/name
    if not path.is_file() or path.is_symlink():raise ValueError('Missing required source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def verify_join(history,mapping,trace):
    if len(history)!=len(mapping) or len(history)!=len(trace):
        raise ValueError('motion, trace and camera frame counts differ')
    for motion,camera,telemetry in zip(history,mapping,trace):
        if ((motion['original_frame'],motion['time_s'])!=(camera['carla_frame'],camera['time_s']) or
                (motion['original_frame'],motion['time_s'])!=(telemetry['frame'],telemetry['time_s'])):
            raise ValueError('original motion, trace and camera frames disagree')


def analyze(attempt):
    root=Path(attempt)
    config=json.loads(required(root,'config.json').read_text())
    suffix=config['selected_case_id'].split('__')[-1]
    case=next((item for item in CASES if item.case_id==suffix),None)
    if case is None:raise ValueError('exact driveway case missing')
    description=config['case']['recording_description']
    original=(root/'acquisition.json').is_file()
    names=('driveway-history.jsonl','driveway-site.json','trace.jsonl','video_frames.jsonl',
           'road.xodr','carla_recorder.log',*[name+'.mkv' for name in CAMERAS])
    if original:
        acquisition=json.loads(required(root,'acquisition.json').read_text())
        for name in names:
            if (acquisition.get(name,{}).get('kind')!='original_native' or
                    acquisition[name].get('sha256')!=sha(required(root,name))):
                raise ValueError('original Native source changed: '+name)
        provenance=json.loads(required(root,'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind')!='native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
    else:
        marker=json.loads(required(root,'diagnostic-source-note.json').read_text())
        if (marker.get('source_kind')!='synthetic_diagnostic_fixture' or
                marker.get('accepted_original_source') is not False or
                marker.get('case_id')!=config['selected_case_id']):
            raise ValueError('synthetic compatibility provenance missing')
    site_path=required(root,'driveway-site.json')
    site=json.loads(site_path.read_text())
    validate_case(site,case)
    history=rows(required(root,'driveway-history.jsonl'))
    mapping=rows(required(root,'video_frames.jsonl'))
    trace=rows(required(root,'trace.jsonl'))
    verify_join(history,mapping,trace)
    if original:
        measured=measure_original(history,site,case)
    else:
        if len(history)<3:raise ValueError('case-specific diagnostic driveway history missing')
        entry=next((i for i in range(1,len(history)) if
                    history[i]['distance_before_sidewalk_edge_m']<=0<
                    history[i-1]['distance_before_sidewalk_edge_m']),None)
        if entry is None:raise ValueError('diagnostic sidewalk entry absent')
        moving=next((i for i in range(entry) if history[i]['speed_mps']>.5),None)
        if moving is None:raise ValueError('diagnostic approach motion absent')
        stops=[i for i in range(moving+1,entry) if history[i]['speed_mps']<=.1]
        last_stop=stops[-1] if stops else None
        conflict=any(row['pedestrian_in_conflict_area'] for row in history)
        yield_seen=any(row['operator_yield_observed'] for row in history)
        if ((last_stop is not None)!=case.stop or conflict!=case.pedestrian or
                yield_seen!=case.yield_to_pedestrian):
            raise ValueError('diagnostic stop, pedestrian or yield contrast absent')
        measured={'case_id':suffix,'frame_count':len(history),
                  'entry_bracket_indices':[entry-1,entry],
                  'last_pre_entry_stop_index':last_stop,
                  'last_stop_distance_before_edge_m':history[last_stop]['distance_before_sidewalk_edge_m']
                  if last_stop is not None else None,
                  'pedestrian_conflict_observed':conflict,
                  'pedestrian_actor_ids':['synthetic-pedestrian'] if conflict else [],
                  'operator_yield_observed':yield_seen,
                  'immediate_proximity_judgment':None,'collision_necessity_judgment':None,
                  'legal_judgment':None,'diagnostic_fixture':True}
    sources={name:sha(root/name) for name in ('driveway-site.json','driveway-history.jsonl',
                                              'video_frames.jsonl','trace.jsonl')}
    values={
        'site_source':lambda row:{'kind':'original_native' if original else 'synthetic_diagnostic'},
        'district_access_context':lambda row:{'district':site['district_type'],'access':site['access_type']},
        'sidewalk_edge':lambda row:{'point':site['edge_point_xy'],'normal':site['edge_normal_xy']},
        'cycle_speed_history':lambda row:row['speed_mps'],
        'edge_distance_history':lambda row:row['distance_before_sidewalk_edge_m'],
        'pedestrian_motion':lambda row:{'ids':row['pedestrian_actor_ids'],
                                        'position':row.get('pedestrian_position_xy')},
        'pedestrian_conflict':lambda row:row['pedestrian_in_conflict_area'],
        'operator_yield':lambda row:row['operator_yield_observed'],
        'camera_frame_map':lambda row:{'frame':row['original_frame'],'time_s':row['time_s']}}
    evidence=[]
    for channel in description['channels']:
        name=channel['name']
        if name not in values:raise ValueError('unknown driveway channel: '+name)
        path=root/('channel-'+name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':row['time_s'],'value':values[name](row)})+'\n'
                                for row in history))
        evidence.append({'name':name,'unit':channel['unit'],'reference':path.name})
    context={item['name']:{'source':site.get(item['name']+'_source_sha256'),
                           'value':site.get(item['name']),'status':'review_pending'}
             for item in description['context_inputs']}
    context_path=root/'channel-context.json';context_path.write_text(json.dumps(context)+'\n')
    for item in description['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':context_path.name})
    from worker_exchange.native_output import physical_result,write_result
    result={'case_id':config['selected_case_id'],'measured_values':measured,
            'target_checks':[{'target':'observed driveway pre-entry stop, pedestrian and yield',
                              'requested':config['case'],'measured':measured,
                              'method':'original source-bound motion' if original else 'synthetic compatibility motion',
                              'tolerance':0,'matched':True,'physical_cause_confirmed':False,
                              'cause_evidence':sources}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'Original independent review pending' if original else 'synthetic compatibility only',
            'physical_failure_flags':[] if original else ['original_driveway_source_absent'],
            'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':description,'recording_evidence':evidence,
            'realized_observables':{},'diagnostic_fixture':not original,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    result=physical_result(root,result);write_result(root,result)
    return {'format':'worker-analysis-report','case_id':config['selected_case_id'],
            'analysis_complete':True,'diagnostic_fixture':not original,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
            'measurements':{'driveway_stop_pedestrian_yield':{'method':'analyze',
                                                              'value':measured,'sources':sources}},
            'physical_checks':result['physical_checks'],
            'realized_observables':result['realized_observables'],
            'limitations':['District, driveway, immediate stop and collision necessity require original independent review.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt),indent=2)+'\n')
