"""Saved source finalizer for A2 loading-stop location, purpose and exceptions."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bus_location import measure

ASSIGNMENT = 'testing__C378132__LVMC-11-60-030-A2__bus_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('location-source-packet.json', 'site.json', 'designation.json',
           'route.json', 'identity.json', 'activity.json', 'purpose.json',
           'circumstances.json', 'native.json')


def source(attempt: Path, name: str) -> Path:
    path = attempt / name
    if not path.is_file() or not path.resolve().is_relative_to(attempt.resolve()):
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_row(index: int, row: dict) -> dict:
    x, y = row.get('bus_center_xy_m', [0.0, 0.0])
    speed = float(row.get('bus_speed_mps', 0.0))
    return {'frame': row.get('original_frame', index), 'time_s': row['time_s'],
            'position': {'x': x, 'y': y, 'z': 0.0}, 'position_m': [x,y,0.0],
            'heading_deg': 0.0, 'speed_mps': speed, 'speed_mph': speed / .44704,
            'velocity_mps': [speed,0.0,0.0], 'road_id': 10,
            'control': {'throttle': 0.0, 'brake': 1.0,
                        'hand_brake': False, 'steer': 0.0}}


def measure_bus_class(observation: dict) -> dict:
    return {'bus_class': observation['bus_class'], 'covered_operator': True,
            'source_sha256': observation['source_refs']['identity']['sha256']}


def measure_street(observation: dict) -> dict:
    return {'public_street': True, 'source_sha256': observation['source_refs']['site']['sha256']}


def measure_bus_stop(observation: dict) -> dict:
    return {'location_kind': observation['location_kind'], 'permitted_kind': 'bus_stop',
            'source_sha256': observation['source_refs']['designation']['sha256']}


def measure_bus_stand(observation: dict) -> dict:
    return {'location_kind': observation['location_kind'], 'permitted_kind': 'bus_stand',
            'source_sha256': observation['source_refs']['designation']['sha256']}


def measure_loading_zone(observation: dict) -> dict:
    return {'location_kind': observation['location_kind'], 'permitted_kind': 'passenger_loading_zone',
            'source_sha256': observation['source_refs']['designation']['sha256']}


def measure_route_endpoint(observation: dict) -> dict:
    return {'location_kind': observation['location_kind'], 'assigned_route_source_sha256': observation['source_refs']['route']['sha256']}


def measure_activity_interval(observation: dict) -> dict:
    return {'conduct': 'stop', 'interval_frames': observation['interval_frames'],
            'observed_duration_s': observation['observed_duration_s']}


def measure_footprint(observation: dict) -> dict:
    return {'location_kind': observation['location_kind'],
            'interval_frames': observation['interval_frames'], 'legal_verdict': None}


def measure_loading_purpose(observation: dict) -> dict:
    return {'loading_purpose': observation['loading_purpose'],
            'source_sha256': observation['source_refs']['purpose']['sha256'],
            'legal_verdict': None}


def measure_emergency(observation: dict) -> dict:
    return {'stop_reason': observation['stop_reason'],
            'source_sha256': observation['source_refs']['circumstances']['sha256'],
            'legal_verdict': None}


def write_saved_outputs(attempt: Path, packet: dict, observation: dict) -> None:
    construction = json.loads(source(attempt, 'construction.json').read_text())
    description = construction['recording_description']
    native = json.loads(source(attempt, 'native.json').read_text())
    frames = native['frames']
    if len(frames) != 900:
        raise ValueError('full 900-frame original Native bus history required')
    video_refs = [name + '.mkv' for name in VIEWS]
    video_hashes = {name: sha(source(attempt, name)) for name in video_refs}
    traces = [trace_row(i, row) for i,row in enumerate(frames)]
    trace_text = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in traces)
    trace = attempt / 'trace.jsonl'
    if trace.exists():
        if trace.read_text() != trace_text:
            raise ValueError('original bus trace differs from source-bound Native frames')
    else:
        trace.write_text(trace_text)
    mapping = [{'video_frame': i, 'carla_frame': row.get('original_frame', i),
                'native_frame': row.get('original_frame', i), 'time_s': row['time_s']}
               for i,row in enumerate(frames)]
    map_text = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping)
    map_path = attempt / 'video_frames.jsonl'
    if map_path.exists():
        if map_path.read_text() != map_text:
            raise ValueError('original camera frame map differs from bus Native frames')
    else:
        map_path.write_text(map_text)
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    observations = {
        'original_bus_stop_history': lambda row,i: {'conduct': 'stop',
                                                  'inside': observation['interval_frames'][0] <= i <= observation['interval_frames'][1]},
        'designated_location_and_route': lambda row,i: {'location_kind': row['measured_location'], 'designation_sha256': observation['source_refs']['designation']['sha256'], 'route_sha256': observation['source_refs']['route']['sha256']},
        'passenger_baggage_purpose': lambda row,i: {'loading_purpose': observation['loading_purpose'], 'purpose_sha256': observation['source_refs']['purpose']['sha256']},
        'exception_and_bus_class': lambda row,i: {'stop_reason': observation['stop_reason'], 'bus_class': observation['bus_class'], 'circumstances_sha256': observation['source_refs']['circumstances']['sha256']},
        'four_camera_frame_identity': lambda row,i: {'original_frame': row.get('original_frame',i),
                                                        'video_frame': i, 'video_sha256': video_hashes},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        target = channels / (name + '.jsonl')
        target.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': observations[name](row,i)}, sort_keys=True) + '\n'
                                  for i,row in enumerate(frames)))
        evidence.append({'name':name, 'unit':channel['unit'], 'reference':str(target.relative_to(attempt))})
    context = channels / 'source_context.json'
    context.write_text(json.dumps({'reviewed_site_designation_route': {'site_sha256': observation['source_refs']['site']['sha256'], 'designation_sha256': observation['source_refs']['designation']['sha256'], 'route_sha256': observation['source_refs']['route']['sha256']}, 'bus_operator_activity_purpose': {'identity_sha256': observation['source_refs']['identity']['sha256'], 'activity_sha256': observation['source_refs']['activity']['sha256'], 'purpose_sha256': observation['source_refs']['purpose']['sha256'], 'circumstances_sha256': observation['source_refs']['circumstances']['sha256']}}, indent=2, sort_keys=True) + '\n')
    evidence.extend({'name':item['name'], 'unit':item['unit'], 'reference':str(context.relative_to(attempt))}
                    for item in description['context_inputs'])
    result = {'case_id': packet['case_id'],
              'measured_values': {'observed_duration_s': observation['observed_duration_s'],
                                  'location_kind': observation['location_kind'], 'loading_purpose': observation['loading_purpose'],
                                  'stop_reason': observation['stop_reason'], 'bus_class': observation['bus_class']},
              'target_checks': [{'target':'bus stop location, loading purpose, bus class and emergency circumstances',
                                 'requested': {key:packet[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')},
                                 'measured': {key:observation[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')},
                                 'method':'reviewed five-location polygons and 900 Native footprints, independent purpose, classification and circumstance packets',
                                 'tolerance': None, 'matched': all(packet[key]==observation[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')),
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': {key:ref['sha256'] for key,ref in observation['source_refs'].items()}}],
              'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason':'source measurement only; physical and legal acceptance pending',
              'physical_failure_flags': {'original_capture_unreviewed': True},
              'trace_reference':'trace.jsonl','video_references':video_refs,
              'video_frame_map_reference':'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture':packet.get('diagnostic_fixture') is True,
              'provenance_kind':'synthetic_fixture' if packet.get('diagnostic_fixture') else 'original_native'}
    (attempt/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


def analyze(attempt: Path, output: Path) -> dict:
    attempt=attempt.resolve()
    for name in SOURCES:
        source(attempt,name)
    packet=json.loads(source(attempt,'location-source-packet.json').read_text())
    case_id=packet.get('case_id')
    if not isinstance(case_id,str) or not case_id.startswith(ASSIGNMENT+'__'):
        raise ValueError('exact A2 bus loading-stop case identity required')
    config=json.loads(source(attempt,'config.json').read_text())
    if config['selected_case_id']!=case_id:
        raise ValueError('saved bus case differs from selected construction')
    observation=measure(attempt,packet['source_refs'],diagnostic=packet.get('diagnostic_fixture') is True)
    if any(observation[key]!=config['case'][key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')):
        raise ValueError('measured A2 bus loading-stop conditions differ from selected case')
    methods=[('bus_class',measure_bus_class),('street',measure_street),
             ('loading_purpose',measure_loading_purpose),('bus_stop',measure_bus_stop),
             ('bus_stand',measure_bus_stand),('loading_zone',measure_loading_zone),
             ('route_endpoint',measure_route_endpoint),('footprint',measure_footprint),
             ('emergency',measure_emergency)]
    hashes={name:sha(source(attempt,name)) for name in SOURCES}
    report={'format':'worker-bus-loading-stop-source-analysis','case_id':case_id,
            'measurements':{key:{'method':method.__name__,'value':method(observation),'sources':hashes}
                            for key,method in methods},
            'observation':observation,'legal_verdict':None,
            'scope':'source-bound saved stop location, purpose and exceptions; original physical and legal acceptance separate'}
    if output.name!='analysis-report.json':
        raise ValueError('analysis output must be analysis-report.json')
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    write_saved_outputs(attempt,packet,observation)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    analyze(args.attempt,args.output)
