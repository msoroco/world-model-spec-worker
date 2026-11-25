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
    'dense_traffic', 'low_visibility', 'ice_or_snow')}
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
                'sight_distance_m', 'precipitation_percent'):
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
    channel = attempt / 'speed-channel.jsonl'
    content = ''.join(json.dumps({'time_s': row['time_s'],
                                  'value': row['ego_speed_mps']}, allow_nan=False) + '\n'
                      for row in report['samples'])
    if channel.exists():
        if channel.read_text() != content:
            raise ValueError('Prior derived speed channel differs from original sources')
    else:
        channel.write_text(content)
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
              'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s',
                                      'reference': 'speed-channel.jsonl'}],
              'source_hashes': report['sources'],
              'capture_evidence_sha256': _sha(attempt / 'capture/evidence.jsonl'),
              'realized_observables': {}}
    result = physical_result(attempt, result)
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
