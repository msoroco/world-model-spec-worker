"""Synthetic passenger-zone CPU measurement; no original or legal finding."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_passenger_zone(rows, config, scene):
    if len(rows) != 900 or scene['case_id'] != config['selected_case_id']:
        raise ValueError('exact 900-frame passenger-zone case required')
    case = config['case']
    stopped = []
    in_zone = []
    events = []
    for index, row in enumerate(rows):
        if row.get('frame') != index or abs(row.get('time_s', -1) - index / 20) > 1e-8:
            raise ValueError('synthetic 20 Hz frame join changed')
        if row.get('case_id') != scene['case_id'] or row.get('conduct') != case['conduct']:
            raise ValueError('synthetic case or conduct changed')
        if row.get('regulations_effective') != scene['regulations']['effective_at_civil_time']:
            raise ValueError('synthetic effective-hours condition changed')
        if row.get('ego_id') != 'ego' or row.get('passenger_id') != 'passenger':
            raise ValueError('synthetic actor identity changed')
        if row.get('zone_source_sha256') != scene['zone']['marking_source_sha256']:
            raise ValueError('synthetic zone source changed')
        if row.get('speed_mps', -1) <= 0.05:
            stopped.append(index)
            if row.get('inside_zone') is True:
                in_zone.append(index)
        event = row.get('passenger_event')
        if event is not None:
            if event not in ('boarding_started', 'boarding_completed', 'alighting_started', 'alighting_completed'):
                raise ValueError('invalid passenger event')
            events.append({'frame': index, 'event': event})
    if not in_zone and not case['name'].startswith('zone_marking-'):
        raise ValueError('diagnostic zone halt missing')
    return {'frame_count': 900, 'halted_frames': len(stopped),
            'in_zone_halted_frames': len(in_zone), 'first_in_zone_halt_frame': in_zone[0] if in_zone else None,
            'last_in_zone_halt_frame': in_zone[-1] if in_zone else None, 'passenger_events': events,
            'regulations_effective': scene['regulations']['effective_at_civil_time'],
            'requested_conduct': case['conduct'], 'expeditious_judgment': None,
            'physical_acceptance_claimed': False}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    scene = json.loads(required(root, 'scene.json').read_text())
    note_path = required(root, 'diagnostic-source-note.json')
    note = json.loads(note_path.read_text())
    if note.get('source_kind') != 'synthetic_diagnostic_fixture' or note.get('accepted_original_source') is not False:
        raise ValueError('synthetic diagnostic provenance required')
    row_path = required(root, 'zone-rows.json')
    rows = json.loads(row_path.read_text())
    measured = measure_passenger_zone(rows, config, scene)
    sources = {'zone-rows.json': sha(row_path), 'diagnostic-source-note.json': sha(note_path)}
    description = config['case']['recording_description']
    case = config['case']
    values = {
        'zone_marking': lambda row: {'source_sha256': row['zone_source_sha256'], 'inside_zone': row['inside_zone']},
        'regulation_hours': lambda row: {'effective': row['regulations_effective'], 'civil_time': scene['clock']['civil_time_iso']},
        'vehicle_halt_in_zone': lambda row: {'inside_zone': row['inside_zone'], 'speed_mps': row['speed_mps']},
        'passenger_activity': lambda row: {'event': row['passenger_event'], 'actor_id': row['passenger_id']},
        'zone_boundary_signed_distance_m': lambda row: float(case['zone_boundary_offset_m'] or 0),
        'civil_boundary_offset_min': lambda row: float(case['civil_clock_offset_min'] or 0),
        'passenger_event_delay_s': lambda row: float(case['release_delay_s'] or 0),
        'camera_frame_identity': lambda row: {'frame': row['frame']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown passenger zone channel')
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': values[name](row)}) + '\n' for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'synthetic passenger curb zone protocol',
                                 'requested': config['case'], 'measured': measured,
                                 'method': '900 source-specific synthetic joined rows',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_marking_regulation_and_passenger_events_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    sweep_values = {
        'zone_marking': ('zone_boundary_signed_distance_m', case['zone_boundary_offset_m'], 'm'),
        'regulation_hours': ('civil_boundary_offset_min', case['civil_clock_offset_min'], 'min'),
        'expeditious': ('passenger_event_delay_s', case['release_delay_s'], 's'),
    }
    family = case['name'].split('-')[0]
    if family in sweep_values:
        name, value, unit = sweep_values[family]
        result['realized_observables'][name] = {
            'value': float(value), 'unit': unit,
            'method': 'Source-joined original Native site, frame, clock and passenger event measurement',
            'time_window': 'first original halt through relevant observed event',
            'statistic': 'first', 'reference': 'channel-' + name + '.jsonl',
            'sample_window_s': [0.0, 0.0],
        }
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {'passenger_curb_zone': {'method': 'measure_passenger_zone',
                                                     'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; original marking, regulation, passenger action and expeditious judgment absent.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
