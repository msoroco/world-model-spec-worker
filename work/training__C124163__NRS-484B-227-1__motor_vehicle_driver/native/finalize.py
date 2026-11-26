"""Finalize saved median sources without converting geometry into a verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from measure_median_turn import measure_attempt

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('median-context.json', 'native-median.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_reference(attempt):
    return measure_attempt(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    for parent in (attempt, *attempt.parents):
        if (parent/'runtime'/'scenario_pipeline').is_dir():
            sys.path.insert(0, str(parent/'runtime'))
            break
    from scenario_pipeline.worker_exchange.native_output import write_result
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Use a fresh saved analysis version')
    for name in ('config.json', 'construction.json', 'trace.jsonl',
                 'body_history.jsonl',
                 'capture/evidence.jsonl', *SOURCES,
                 *(name+'.mkv' for name in CAMERAS)):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    case = config.get('selected_case_id', config.get('case_id'))
    if case != construction.get('case_id'):
        raise ValueError('Exact saved case identity differs')
    metric = measure_reference(attempt)
    target = config['case_target']['physical_target']
    counts = metric['occupancy_frames']
    matched = counts['opening'] > 0 and counts['barrier'] == 0 if target == 'opening' else counts['barrier'] > 0
    rows = [json.loads(line) for line in (attempt/'native-median.jsonl').read_text().splitlines()]
    context = json.loads((attempt/'median-context.json').read_text())
    channels = attempt/'channels'
    channels.mkdir()
    channel_values = {
        'ego_pose': lambda row: row['ego'],
        'median_geometry': lambda row: {'median_bounds_m': context['median_bounds_m'],
            'opening_bounds_m': context['opening_bounds_m'],
            'barrier_bounds_m': context['barrier_bounds_m'],
            'native_roadways': context.get('native_roadways')},
        'roadway_occupancy': lambda row: {'body_xy_m': row['ego']['body_xy_m'],
            'right_hand_roadway_y_max_m': -2, 'opposite_roadway_y_min_m': 2},
        'turn_history': lambda row: {'yaw_deg': row['ego'].get('yaw_deg'),
            'speed_mps': row['ego']['speed_mps'],
            'route_target_index': row.get('route_target_index')},
        'administrative_context': lambda row: {
            'public_authority_establishment': context['public_authority_establishment'],
            'authority_source_review_sha256': metric['source_review_sha256']},
        'median_crossing_measurement': lambda row: {'metric': metric,
            'source_frame': row['video_frame']},
    }
    evidence = []
    for name, value in channel_values.items():
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                    'value': value(row)}, allow_nan=False)+'\n')
        evidence.append({'name': name, 'unit': 'structured',
                         'reference': 'channels/'+path.name})
    result = {'case_id': case, 'measured_values': metric,
        'target_checks': [{'target': 'full-body median crossing at requested station',
            'requested': config['case_target'], 'measured': metric,
            'method': 'measure_reference', 'tolerance': {}, 'matched': matched,
            'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False,
        'behavior_attempted': not metric['diagnostic_fixture'],
        'maneuver_completed': not metric['diagnostic_fixture'] and matched,
        'termination_reason': '600-frame saved median source; physical and authority review pending',
        'physical_failure_flags': ['Original body geometry, actual route and pixel visibility require review'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if metric['diagnostic_fixture'] else 'native',
        'accepted': False}
    write_result(attempt, result)
    measurements = {name: {'method': 'measure_reference', 'value': metric,
        'sources': {source: sha(attempt/source) for source in SOURCES}}
        for name in ('roadway_duty', 'divider_prohibition', 'turn_event',
                     'opening_exception', 'authority_context')}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': measurements, 'source_complete': True,
              'diagnostic_fixture': metric['diagnostic_fixture'],
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
