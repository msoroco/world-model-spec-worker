"""Saved-only, original-source two-pass measurement for C178759.

Road geometry and event requests yield unreviewed engineering candidates only.
Pavement material, speeding law, immediate hazard and offense remain undecided.
"""

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

from aggressive_sequence import measure_sequence
from right_pass_source import candidates

CASE_ID = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass'
CAMERAS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def _required(root, name):
    path = root/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: '+path.name) from error


def measure_two_right_passes(trace, right_pass, frame_map):
    joined = candidates(right_pass, frame_map)
    if joined['status'] == 'candidate':
        envelope = measure_sequence(trace, joined['episodes'], [], [])
        if not envelope['two_distinct_right_passing_episodes_measured']:
            raise ValueError('Two original right-pass episodes missing')
    else:
        envelope = None
    return {'source_status':joined['status'],
            'source_reason':joined.get('reason'),
            'fixed_overtaken_actor_id':joined['fixed_overtaken_actor_id'],
            'episodes':joined['episodes'],
            'event_envelope':envelope,
            'pavement_surface_decided':False,
            'speeding_violation_decided':False,
            'right_pass_violation_decided':False,
            'immediate_hazard_decided':False,
            'aggressive_driving_decided':False}


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _required(root,'config.json')
    config = json.loads(config_path.read_text())
    if (config.get('selected_case_id') != CASE_ID or
            (config.get('law_id'),config.get('cell_id'),config.get('actor')) !=
            ('NRS-484B-650-1','C178759','motor_vehicle_driver')):
        raise ValueError('Wrong exact two-pass case identity')
    paths = {}
    for name in ('video_frames.jsonl','driving_trace.jsonl',
                 'right_pass_sources.jsonl','following_sources.jsonl',*CAMERAS):
        paths[name] = _required(root,name)
    frame_map = _rows(paths['video_frames.jsonl'][0])
    trace = _rows(paths['driving_trace.jsonl'][0])
    pass_rows = _rows(paths['right_pass_sources.jsonl'][0])
    following = _rows(paths['following_sources.jsonl'][0])
    if not frame_map or len(frame_map) != len(trace) or len(trace) != len(following):
        raise ValueError('Original trace/following/frame coverage differs')
    for i,(frame,motion,body) in enumerate(zip(frame_map,trace,following)):
        if (frame.get('video_frame') != i or
                (frame.get('carla_frame'),frame.get('time_s')) !=
                (motion.get('frame'),motion.get('time_s')) or
                (motion.get('frame'),motion.get('time_s')) !=
                (body.get('frame'),body.get('time_s'))):
            raise ValueError('Original trace, following and video frame join differs')
        road = pass_rows[i]
        if ((road.get('ego_actor_id'),road.get('fixed_overtaken_actor_id')) !=
                (body.get('ego',{}).get('actor_id'),body.get('lead',{}).get('actor_id'))):
            raise ValueError('Original ego/fixed vehicle identity join differs')
        ego_xy=road.get('ego_xy_m')
        lead_xy=road.get('lead_xy_m')
        if (not isinstance(ego_xy,list) or not isinstance(lead_xy,list) or
                len(ego_xy)!=2 or len(lead_xy)!=2 or
                any(abs(a-b)>1e-3 for a,b in zip(ego_xy,[motion['x_m'],motion['y_m']])) or
                any(abs(a-b)>1e-3 for a,b in zip(ego_xy,body['ego']['position_m'][:2])) or
                any(abs(a-b)>1e-3 for a,b in zip(lead_xy,body['lead']['position_m'][:2]))):
            raise ValueError('Original actor/road path geometry join differs')
        edge=road.get('mapped_road_edge_xy_m')
        axis=road.get('right_axis_xy')
        if (not isinstance(edge,list) or not isinstance(axis,list) or len(edge)!=2 or len(axis)!=2 or
                abs((ego_xy[0]-edge[0])*axis[0]+(ego_xy[1]-edge[1])*axis[1]-
                    road['right_of_mapped_road_edge_m'])>1e-3):
            raise ValueError('Mapped edge clearance differs from original geometry')
    observed = measure_two_right_passes(trace,pass_rows,frame_map)
    return {'format':'worker-analysis-report','case_id':CASE_ID,
            'measurements':{'two_right_pass_observation':{
                'method':'measure_two_right_passes','value':observed,
                'sources':{name:digest for name,(_,digest) in paths.items()}}},
            'limitations':['Mapped road edge is not proof of paved surface.',
                           'Original speeding, right-pass legality, immediate hazard and composite offense require independent review.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root/'config.json').read_text())
    description = config.get('case',{}).get('recording_description')
    if not isinstance(description,dict):
        raise ValueError('Exact recording description missing')
    trace = _rows(root/'driving_trace.jsonl')
    passes = _rows(root/'right_pass_sources.jsonl')
    if len(trace) != len(passes):
        raise ValueError('Original path and road source differ')
    distance, path_rows, previous = 0.0, [], None
    for row in trace:
        if previous is not None:
            distance += hypot(row['x_m']-previous['x_m'],row['y_m']-previous['y_m'])
        path_rows.append({'frame':row['frame'],'time_s':row['time_s'],'value':distance})
        previous = row
    path = root/'path_length_m.jsonl'
    edge = root/'mapped_road_edge_clearance_m.jsonl'
    if path.exists() or edge.exists():
        raise ValueError('Retain prior derived source channels')
    path.write_text(''.join(json.dumps(row)+'\n' for row in path_rows))
    edge.write_text(''.join(json.dumps({'frame':row['frame'],'time_s':row['time_s'],
                                       'value':row['right_of_mapped_road_edge_m']})+'\n'
                            for row in passes))
    context = root/'original_actor_and_road_context.json'
    context.write_text(json.dumps({'original_actor_and_road_context':{
        'right_pass_source':'right_pass_sources.jsonl',
        'right_pass_source_sha256':sha256((root/'right_pass_sources.jsonl').read_bytes()).hexdigest(),
        'fixed_overtaken_actor_id':passes[0]['fixed_overtaken_actor_id'],
        'pavement_surface_review_pending':True},
        'fixed_overtaken_vehicle':{'actor_id':passes[0]['fixed_overtaken_actor_id'],
            'source':'right_pass_sources.jsonl'},
        'paved_versus_traveled_boundary':{'mapped_driving_edge':'right_pass_sources.jsonl',
            'mapped_road_edge':'right_pass_sources.jsonl',
            'pavement_material_review':'pending original RGB review'}},indent=2)+'\n')
    legal_context=root/'governing_cross_referenced_rule.json'
    legal_context.write_text(json.dumps({'governing_cross_referenced_rule':{
        'source':'frozen NRS 484B.650(1) and NRS 484B.210 predicate context',
        'status':'independent review pending','speeding_judgment':None,
        'right_pass_judgment':None,'hazard_judgment':None}},indent=2)+'\n')
    observed = report['measurements']['two_right_pass_observation']['value']
    return {'case_id':CASE_ID,'measured_values':{'two_right_pass_observation':observed},
        'target_checks':[{'target':'two distinct right passes of fixed vehicle inside one-mile conduct envelope',
            'requested':'two separate off-pavement right-pass requests with intervening reset',
            'measured':observed,'method':'source-joined original 20 Hz actors, road edges and route path',
            'tolerance':None,'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':'Original pavement surface and legal predicates await independent review'}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
        'termination_reason':'Saved original geometry measured; physical and legal acceptance pending',
        'physical_failure_flags':{'detection_validated':False},
        'trace_reference':'trace.jsonl','video_references':list(CAMERAS),
        'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
        'recording_evidence':[
            {'name':'path_length_m','unit':'m','reference':path.name,'sha256':sha256(path.read_bytes()).hexdigest()},
            {'name':'mapped_road_edge_clearance_m','unit':'m','reference':edge.name,'sha256':sha256(edge.read_bytes()).hexdigest()},
            {'name':'original_actor_and_road_context','unit':'source packet','reference':context.name,'sha256':sha256(context.read_bytes()).hexdigest()},
            {'name':'fixed_overtaken_vehicle','unit':'Native actor ID','reference':context.name,'sha256':sha256(context.read_bytes()).hexdigest()},
            {'name':'paved_versus_traveled_boundary','unit':'source geometry and RGB pixels','reference':context.name,'sha256':sha256(context.read_bytes()).hexdigest()},
            {'name':'governing_cross_referenced_rule','unit':'sourced legal context','reference':legal_context.name,'sha256':sha256(legal_context.read_bytes()).hexdigest()}],
        'realized_observables':{'path_length_m':{'unit':'m','method':'original 20 Hz ego path integration',
            'time_window':'full original driving trace','statistic':'last','reference':path.name,
            'value':distance,'sample_window_s':[trace[0]['time_s'],trace[-1]['time_s']]}},
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=analyze(args.attempt)
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior source-bound analysis report')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__':main()
