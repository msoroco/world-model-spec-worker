"""Finalize only sealed opposite-direction meeting sources or labeled CPU fixtures."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from measure_saved import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('pavement-survey.json', 'native-motion.jsonl', 'video_frames.jsonl')
KEY = 'opposite_direction_paved_half_measurement'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_reference(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    for parent in (attempt, *attempt.parents):
        if (parent / 'runtime' / 'scenario_pipeline').is_dir():
            sys.path.insert(0, str(parent / 'runtime'))
            break
    from scenario_pipeline.worker_exchange.native_output import write_result
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
    survey = json.loads((attempt / 'pavement-survey.json').read_text())
    values = {
        'ego_body': lambda row: row['ego'],
        'oncoming_body': lambda row: row['oncoming'],
        'paved_road_context': lambda row: survey,
        'meeting_motion': lambda row: {
            'ego_velocity_xyz_mps': row['ego']['velocity_xyz_mps'],
            'oncoming_velocity_xyz_mps': row['oncoming']['velocity_xyz_mps'],
            'ego_center_xyz_m': row['ego']['center_xyz_m'],
            'oncoming_center_xyz_m': row['oncoming']['center_xyz_m']},
    }
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for name, get_value in values.items():
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': get_value(row)}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': 'structured',
                         'reference': 'channels/' + path.name})
    requested = 1.0 if case.endswith('1.00') else None
    if requested is None: raise ValueError('Wrong safe reference case')
    measured = metric['ego_right_paved_half_footprint_fraction_min']
    result = {
        'case_id': case, 'measured_values': metric,
        'target_checks': [{'target': 'ego body fraction in right paved half',
                           'requested': requested, 'measured': measured,
                           'method': 'measure_reference', 'tolerance': .03,
                           'matched': abs(requested-measured) <= .03,
                           'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False,
        'behavior_attempted': not metric['diagnostic_fixture'],
        'maneuver_completed': not metric['diagnostic_fixture'],
        'termination_reason': ('600 retained frames; original pavement and physical review pending'
                               if not metric['diagnostic_fixture'] else
                               '600-frame synthetic CPU diagnostic'),
        'physical_failure_flags': ['Original paved bounds, physical feasibility and statutory as-nearly-as-possible review pending'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'provenance_kind': 'synthetic_local_diagnostic' if metric['diagnostic_fixture'] else 'native',
        'accepted': False}
    write_result(attempt, result)
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {KEY: {'method': 'measure_reference', 'value': metric,
                                     'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'diagnostic_fixture': metric['diagnostic_fixture'],
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
