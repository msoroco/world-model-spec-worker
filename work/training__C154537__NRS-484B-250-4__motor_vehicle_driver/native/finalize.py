"""Saved-only finalization of C154537 original or explicitly synthetic sources."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from measure_saved import measure

SOURCES = ('scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
KEY = 'inoperative_signal_visible_point_measurement'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_reference(attempt):
    return measure(attempt)


def finalize(attempt, output):
    for parent in (Path(attempt).resolve(), *Path(attempt).resolve().parents):
        if (parent / 'runtime' / 'scenario_pipeline').is_dir():
            sys.path.insert(0, str(parent / 'runtime'))
            break
    from scenario_pipeline.worker_exchange.native_output import write_result
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved analysis version')
    for name in ('config.json', 'construction.json', 'trace.jsonl',
                 'capture/evidence.jsonl', *SOURCES,
                 *(camera + '.mkv' for camera in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id', config.get('case_id'))
    if case != construction.get('case_id'):
        raise ValueError('Exact saved case identity differs')
    metric = measure_reference(attempt)
    rows = [json.loads(line) for line in (attempt / 'native-motion.jsonl').read_text().splitlines()]
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    channel_values = {
        'ego_front': lambda row: row['ego_front_x_m'],
        'ego_speed': lambda row: row['ego_speed_mps'],
        'governing_signal': lambda row: row['signal_state'],
        'other_vehicle': lambda row: row.get('other'),
        'driver_view_rays': lambda row: None,
    }
    survey = json.loads((attempt / 'scene-survey.json').read_text())
    rays_by_frame = {row['native_frame']: row for row in survey['driver_view_samples']}
    channel_values['driver_view_rays'] = lambda row: rays_by_frame.get(row['native_frame'])
    units = {'ego_front': 'm', 'ego_speed': 'm/s', 'governing_signal': 'structured',
             'other_vehicle': 'structured', 'driver_view_rays': 'structured'}
    for name, get_value in channel_values.items():
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': get_value(row)}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': units[name],
                         'reference': 'channels/' + path.name})
    wanted_stop = case.endswith('controlled_1')
    observed_stop = metric['complete_cessation_sample_before_entry']
    result = {'case_id': case, 'measured_values': metric,
              'target_checks': [{'target': 'complete cessation before surveyed visible point',
                  'requested': wanted_stop, 'measured': observed_stop,
                  'method': 'measure_reference', 'tolerance': None,
                  'matched': wanted_stop == observed_stop,
                  'physical_cause_confirmed': False,
                  'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False,
              'behavior_attempted': not metric['diagnostic_fixture'],
              'maneuver_completed': not metric['diagnostic_fixture'] and metric['entry_frame'] is not None,
              'termination_reason': '600 retained frames; original physical review pending'
                                    if not metric['diagnostic_fixture'] else
                                    '600-frame synthetic CPU diagnostic',
              'physical_failure_flags': ['Official device, through highway and driver-view legal review pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if metric['diagnostic_fixture'] else 'native',
              'accepted': False}
    write_result(attempt, result)
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {KEY: {'method': 'measure_reference',
                                     'value': metric,
                                     'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True,
              'diagnostic_fixture': metric['diagnostic_fixture'],
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
