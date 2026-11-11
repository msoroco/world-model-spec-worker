"""Saved-only C109749 analysis from original Native junction sources."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measurements import analyze, _body_intersects
from reciprocal_no_yield_observation import observe

CAMERAS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_initial_yield(report):
    return {'initial_opposing_presence_frames':report['oncoming_presence_frames'],
            'initial_opposing_clearance_frame':report['initial_oncoming_clearance_frame'],
            'ego_low_speed_frames':report['ego_low_speed_frames']}


def measure_signal_turn(report):
    return {'ego_left_indicator_frames':report['ego_left_indicator_frames'],
            'ego_turn_start_frame':report['ego_turn_start_frame']}


def measure_reciprocal_yield(report):
    return {'later_opposing_low_speed_frames':report['reciprocal_low_speed_frames'],
            'later_opposing_first_entry_frame':report['reciprocal_first_in_intersection_frame'],
            'stopped_outside_during_turn':report['reciprocal_stopped_outside_during_turn']}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result, physical_result
    attempt,output = Path(attempt),Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    required = ('config.json','intersection_geometry.json','interaction_history.jsonl',
                'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl',*CAMERAS)
    for name in required:
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    if config.get('selected_case_id') != 'testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_no_yield':
        raise ValueError('Exact C109749 selected case required')
    description = config.get('recording_description')
    if not isinstance(description,dict) or not description.get('channels'):
        raise ValueError('Selected recording description required')
    report = analyze(attempt)
    entry_observation = observe(attempt)
    raw = [json.loads(line) for line in (attempt/'interaction_history.jsonl').read_text().splitlines() if line.strip()]
    geometry = json.loads((attempt/'intersection_geometry.json').read_text())
    polygon = geometry['intersection_polygon_xy_m']
    channel_root = attempt/'channels'
    channel_root.mkdir()
    streams = {
      'ego_speed':lambda row:math.hypot(*row['ego']['velocity_xy_mps']),
      'oncoming_speed':lambda row:math.hypot(*row['oncoming']['velocity_xy_mps']),
      'reciprocal_speed':lambda row:math.hypot(*row['reciprocal']['velocity_xy_mps']),
      'ego_heading':lambda row:row['ego_heading_deg'],
      'ego_left_indicator':lambda row:row['ego_left_indicator'],
      'ego_in_intersection':lambda row:_body_intersects(row['ego']['body_vertices_xy_m'],polygon),
      'initial_oncoming_in_intersection':lambda row:_body_intersects(row['oncoming']['body_vertices_xy_m'],polygon),
      'reciprocal_in_intersection':lambda row:_body_intersects(row['reciprocal']['body_vertices_xy_m'],polygon),
    }
    for name,extract in streams.items():
        with (channel_root/(name+'.jsonl')).open('x') as stream:
            for row in raw:
                stream.write(json.dumps({'time_s':row['time_s'],'original_frame':row['frame'],
                                         'value':extract(row)},allow_nan=False)+'\n')
    (channel_root/'junction_context.json').write_text(json.dumps({'junction_context':{
      'native_junction_id':geometry.get('native_junction_id'),
      'intersection_polygon_xy_m':polygon,
      'boundary_limit':geometry.get('boundary_limit'),
      'legal_immediate_hazard':'unresolved'}},indent=2)+'\n')
    units = {'ego_speed':'m/s','oncoming_speed':'m/s','reciprocal_speed':'m/s',
             'ego_heading':'deg','ego_left_indicator':'boolean',
             'ego_in_intersection':'boolean','initial_oncoming_in_intersection':'boolean',
             'reciprocal_in_intersection':'boolean'}
    evidence = [{'name':name,'unit':unit,'reference':'channels/'+name+'.jsonl'}
                for name,unit in units.items()]
    evidence.append({'name':'junction_context','unit':'structured record',
                     'reference':'channels/junction_context.json'})
    reciprocal = report['reciprocal_stopped_outside_during_turn']
    result = {'case_id':config['selected_case_id'],
      'measured_values':{'initial_oncoming_clearance_frame':report['initial_oncoming_clearance_frame'],
                         'ego_turn_start_frame':report['ego_turn_start_frame'],
                         'reciprocal_stopped_outside_during_turn':reciprocal,
                         'later_opposing_entry_frame':entry_observation['later_opposing_entry_frame'],
                         'ego_exit_frame':entry_observation['ego_exit_frame']},
      'target_checks':[{'target':'reciprocal_stopped_outside_during_turn',
                        'requested':False,'measured':reciprocal,
                        'method':'original three-actor body, velocity, heading and frame joins',
                        'tolerance':0,'matched':not reciprocal,'physical_cause_confirmed':False,
                        'cause_evidence':['interaction_history.jsonl','intersection_geometry.json',
                                          'video_frames.jsonl']}],
      'entry_observation':entry_observation,
      'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
      'termination_reason':'saved original-source analysis; legal judgment remains separate',
      'physical_failure_flags':['legal immediate-hazard and reciprocal right-of-way unresolved',
                                'real camera visibility requires independent review'],
      'trace_reference':'trace.jsonl','video_references':list(CAMERAS),
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,'recording_evidence':evidence,
      'source_evidence_hashes':report['sources'],
      'capture_evidence_sha256':_sha(attempt/'capture/evidence.jsonl'),
      'realized_observables':{}}
    result = physical_result(attempt,result)
    selected_sources = {name:report['sources'][name] for name in
                        ('intersection_geometry.json','interaction_history.jsonl','video_frames.jsonl')}
    measurements = {key:{'method':method.__name__,'value':method(report),'sources':selected_sources}
                    for key,method in [('initial_yield_sequence',measure_initial_yield),
                                       ('signal_and_turn_sequence',measure_signal_turn),
                                       ('reciprocal_yield_observation',measure_reciprocal_yield)]}
    analysis = {'format':'worker-left-turn-analysis','case_id':config['selected_case_id'],
                'measurements':measurements,'source_report':report,'source_hashes':report['sources'],
                'physical_checks':result['physical_checks'],
                'legal_verdict_asserted':False}
    write_result(attempt,result)
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
    return analysis


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)


if __name__ == '__main__':
    main()
