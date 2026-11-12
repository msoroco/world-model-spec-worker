"""Saved-only center-lane left-turn preparation from original route and signal sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import analyze as analyze_lanes, build_result as build_lane_result


def _source(root,name):
    path=Path(root)/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return path,sha256(path.read_bytes()).hexdigest()


def measure_turn_sources(attempt):
    root=Path(attempt)
    names=('left_turn_frames.jsonl','left_turn_plan.json','three_lane_frames.jsonl',
           'three_lane_context.json','three_lane_map_readback.json',
           'trace.jsonl','video_frames.jsonl')
    paths={name:_source(root,name) for name in names}
    plan=json.loads(paths['left_turn_plan.json'][0].read_text())
    readback=json.loads(paths['three_lane_map_readback.json'][0].read_text())
    if (plan.get('approach_road_id')!=readback.get('road_id') or
            plan.get('approach_center_lane_id')!=readback.get('lane_ids',{}).get('center') or
            plan.get('junction_entered') is not True or
            not 45<=plan.get('turn_angle_deg',0)<=135 or
            plan.get('approach_road_id')==plan.get('left_exit_road_id') or
            plan.get('physical_turn_completed') is not None):
        raise ValueError('Original mapped left-turn connection missing')
    turns=[json.loads(line) for line in paths['left_turn_frames.jsonl'][0].read_text().splitlines() if line.strip()]
    lanes=[json.loads(line) for line in paths['three_lane_frames.jsonl'][0].read_text().splitlines() if line.strip()]
    if len(turns)<2 or len(turns)!=len(lanes):
        raise ValueError('Original left-turn and three-lane frame counts differ')
    observations=[]
    previous=None
    for row,lane in zip(turns,lanes):
        if ((row.get('frame'),row.get('time_s'),row.get('ego_actor_id')) !=
                (lane.get('frame'),lane.get('time_s'),lane.get('ego_actor_id')) or
                row.get('left_indicator_requested') is not True or
                row.get('left_indicator_readback') is not True):
            raise ValueError('Original left-turn signal or frame identity missing')
        distance=row.get('distance_to_approach_end_m')
        if type(distance) not in (int,float) or distance<0 or (previous is not None and distance>previous+0.5):
            raise ValueError('Original left-turn approach distance invalid')
        previous=distance
        observations.append({'frame':row['frame'],'time_s':row['time_s'],
                             'distance_to_approach_end_m':distance,
                             'left_indicator_readback':True})
    return {'format':'worker-left-turn-preparation-observation',
            'sources':{name:checksum for name,(_,checksum) in paths.items()},
            'observations':observations,
            'mapped_turn_angle_deg':plan['turn_angle_deg'],
            'mapped_left_exit_road_id':plan['left_exit_road_id'],
            'approach_distance_reduced':observations[-1]['distance_to_approach_end_m']<observations[0]['distance_to_approach_end_m'],
            'physical_turn_completed':None,'legal_left_turn_exception_judgment':None}


def analyze(attempt):
    report=analyze_lanes(attempt)
    if not report['case_id'].endswith('__center_left_turn'):
        raise ValueError('Wrong exact center left-turn identity')
    measured=measure_turn_sources(attempt)
    report['measurements']['left_turn_observation']={
        'method':'measure_turn_sources','value':measured,'sources':measured['sources']}
    return report


def build_result(attempt,report):
    result=build_lane_result(attempt,report)
    measured=report['measurements']['left_turn_observation']['value']
    channel=Path(attempt)/'left_turn_observation.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived left-turn channel')
    channel.write_text(''.join(json.dumps({'frame':row['frame'],'time_s':row['time_s'],
        'value':row['distance_to_approach_end_m']},allow_nan=False)+'\n'
        for row in measured['observations']))
    result['measured_values']['left_turn_observation']=measured
    result['recording_evidence'].append({'name':'left_turn_observation','unit':'meters',
        'reference':channel.name,'sha256':sha256(channel.read_bytes()).hexdigest()})
    result['realized_observables']['left_turn_observation']={
        'unit':'meters','method':'original 20 Hz approach and left-indicator source',
        'time_window':'all original frames','statistic':'approach_distance_reduction',
        'reference':channel.name,
        'value':(measured['observations'][0]['distance_to_approach_end_m']-
                 measured['observations'][-1]['distance_to_approach_end_m']),
        'sample_window_s':[measured['observations'][0]['time_s'],
                           measured['observations'][-1]['time_s']]}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior left-turn analysis')
    report=analyze(args.attempt)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__':
    main()
