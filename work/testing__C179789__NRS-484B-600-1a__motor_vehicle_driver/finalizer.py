"""Finalize original speed and roadway-condition samples from a saved attempt.

The engineering target ranges describe the planned scene. They do not decide
whether the speed was reasonable or proper under NRS 484B.600(1)(a).
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from conditions_measurements import analyze


ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
EXACT_CASES = {ASSIGNMENT + '__' + suffix for suffix in (
    'dry_open_traffic', 'wet_same_traffic', 'narrow_same_traffic',
    'dense_traffic', 'low_visibility', 'ice_or_snow', 'dry_4mps', 'dry_6mps')}
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_peak_speed(report):
    return max(row['ego_speed_mps'] for row in report['samples'])


def _values(report, key):
    if key == 'longitudinal_body_gap_m':
        return [row['surrounding_traffic'][0][key] for row in report['samples']]
    return [row[key] for row in report['samples']]


def _target_checks(config, report):
    target = config['condition_target']
    checks = []
    for key in ('lane_width_m', 'longitudinal_body_gap_m',
                'sight_distance_m', 'precipitation_percent',
                'fog_density_percent', 'fog_distance_m'):
        if key.startswith('fog_') and key not in target:
            continue
        low, high = target[key]
        values = _values(report, key)
        matched = all(low <= value <= high for value in values)
        checks.append({'target': key, 'requested': [low, high],
                       'measured': {'minimum': min(values), 'maximum': max(values)},
                       'method': 'all original frame-specific observations',
                       'tolerance': 0, 'matched': matched,
                       'physical_cause_confirmed': False,
                       'cause_evidence': ['condition_history.jsonl', 'road_context.json']})
    surfaces = [row['surface'] for row in report['samples']]
    checks.append({'target': 'surface', 'requested': target['surface'],
                   'measured': sorted(set(surfaces)),
                   'method': 'original surface document and frame join',
                   'tolerance': 0,
                   'matched': all(value == target['surface'] for value in surfaces),
                   'physical_cause_confirmed': False,
                   'cause_evidence': ['road_context.json', 'condition_history.jsonl',
                                      report['surface_source_path']]})
    requested = config['requested_speed_mps']
    peak = measure_peak_speed(report)
    tolerance = config.get('engineering_target_tolerance_mps', 1.0)
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Invalid engineering speed tolerance')
    checks.append({'target': 'sampled_peak_speed_mps', 'requested': requested,
                   'measured': peak, 'method': 'original actor.get_velocity 3D magnitude',
                   'tolerance': tolerance, 'matched': abs(peak - requested) <= tolerance,
                   'physical_cause_confirmed': False,
                   'cause_evidence': ['condition_history.jsonl', 'video_frames.jsonl']})
    return checks


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    for name in ('config.json', 'trace.jsonl', 'capture/evidence.jsonl', *CAMERAS):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    if config.get('selected_case_id') not in EXACT_CASES:
        raise ValueError('Wrong exact speed/conditions case')
    if not config.get('recording_description'):
        raise ValueError('Missing recording description')
    requested = config.get('requested_speed_mps')
    if type(requested) not in (int, float) or not math.isfinite(requested) or requested <= 0:
        raise ValueError('Missing requested speed')
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    report = analyze(attempt)
    report['surface_source_path'] = json.loads((attempt / 'road_context.json').read_text())[
        'road_surface_source']['path']
    checks = _target_checks(config, report)
    channel_values = {
        'ego_speed_mps': lambda row: row['ego_speed_mps'],
        'lead_speed_mps': lambda row: row['surrounding_traffic'][0]['speed_mps'],
        'longitudinal_body_gap_m': lambda row: row['surrounding_traffic'][0]['longitudinal_body_gap_m'],
        'lane_width_m': lambda row: row['lane_width_m'],
        'surface': lambda row: row['surface'],
        'precipitation_percent': lambda row: row['precipitation_percent'],
        'sight_distance_m': lambda row: row['sight_distance_m'],
        'curvature_per_m': lambda row: row['curvature_per_m'],
        'fog_density_percent': lambda row: row.get('fog_density_percent', 0.0),
        'fog_distance_m': lambda row: row.get('fog_distance_m', 0.0),
    }
    units = {channel['name']: channel['unit'] for channel in config['recording_description']['channels']}
    recording_evidence = []
    for name, value in channel_values.items():
        reference = 'speed-channel.jsonl' if name == 'ego_speed_mps' else name + '-channel.jsonl'
        channel = attempt / reference
        content = ''.join(json.dumps({'time_s': row['time_s'], 'value': value(row)},
                                     allow_nan=False) + '\n' for row in report['samples'])
        if channel.exists():
            if channel.read_text() != content:
                raise ValueError('Prior derived channel differs from original sources: ' + name)
        else:
            channel.write_text(content)
        recording_evidence.append({'name': name, 'unit': units[name], 'reference': reference})
    context = attempt / 'road-context-channel.json'
    context_content = json.dumps({'road_context': json.loads((attempt / 'road_context.json').read_text())},
                                 indent=2, allow_nan=False) + '\n'
    if context.exists():
        if context.read_text() != context_content:
            raise ValueError('Prior derived road context differs from original source')
    else:
        context.write_text(context_content)
    recording_evidence.append({'name': 'road_context', 'unit': 'structured record',
                               'reference': 'road-context-channel.json'})
    peak = measure_peak_speed(report)
    result = {'case_id': config['selected_case_id'],
              'measured_values': {'sampled_peak_speed_mps': peak,
                                  'sampled_peak_speed_mph': peak * 2.2369362921,
                                  'condition_sample_count': len(report['samples']),
                                  'sampled_diagnostic_stop_distance_exceeds_sight':
                                      any(row['diagnostic_stop_distance_exceeds_sight']
                                          for row in report['samples']),
                                  'reasonable_or_proper_judgment': 'unresolved'},
              'target_checks': checks, 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved source analysis; independent physical audit pending',
              'physical_failure_flags': ['surface, weather, visibility and traffic require physical review',
                                         'reasonable-or-proper legal judgment unresolved'],
              'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': recording_evidence,
              'source_hashes': report['sources'],
              'capture_evidence_sha256': _sha(attempt / 'capture/evidence.jsonl'),
              'realized_observables': {'ego_speed_mps': {
                  'unit': 'm/s', 'method': 'original Native ego velocity samples',
                  'time_window': 'entire captured interval', 'statistic': 'max',
                  'reference': 'speed-channel.jsonl', 'value': peak,
                  'sample_window_s': [report['samples'][0]['time_s'],
                                      report['samples'][-1]['time_s']]}}}
    result = physical_result(attempt, result)
    result['realized_observables']['ego_speed_mps'] = {
        'unit': 'm/s', 'method': 'original Native ego velocity samples',
        'time_window': 'entire captured interval', 'statistic': 'max',
        'reference': 'speed-channel.jsonl', 'value': peak,
        'sample_window_s': [report['samples'][0]['time_s'],
                            report['samples'][-1]['time_s']]}
    analysis = {'format': 'worker-basic-speed-conditions-analysis',
                'case_id': config['selected_case_id'],
                'measurements': {'sampled_peak_speed_mps': {
                    'method': 'measure_peak_speed', 'value': peak,
                    'sources': report['sources']}},
                'source_report': report, 'physical_checks': result['physical_checks'],
                'realized_observables': result['realized_observables'],
                'physical_acceptance_claimed': False,
                'legal_conclusion': 'unresolved'}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
