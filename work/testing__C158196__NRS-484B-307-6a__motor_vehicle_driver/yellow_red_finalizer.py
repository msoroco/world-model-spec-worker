"""Saved-only Yellow/Red body-entry analysis of original Native source rows.

The case target is an engineering timing target. No stopping-feasibility,
head-visibility, or legal judgment is inferred from these numeric sources.
"""
import argparse
import json
import sys
from pathlib import Path

from red_entry_measurements import analyze
from yellow_red_policy import CASES, DURATION_FRAMES, RATE_HZ


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _write_jsonl(path, rows):
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n')


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    cfg = json.loads((attempt / 'config.json').read_text())
    case_id = cfg['selected_case_id']
    if cfg['case']['case_id'] != case_id or case_id not in cfg['supported_case_ids']:
        raise ValueError('Selected case/config identity mismatch')
    suffix = case_id.removeprefix(attempt_case_prefix())
    if suffix not in CASES:
        raise ValueError('Unsupported exact yellow/red case')
    if cfg['rate_hz'] != RATE_HZ or round(cfg['duration_s'] * RATE_HZ) != DURATION_FRAMES:
        raise ValueError('Selected rate/duration differs from source measurement plan')
    report = analyze(attempt)
    samples = report['samples']
    if len(samples) != DURATION_FRAMES:
        raise ValueError('Incomplete selected-case original source interval')
    frame_index = {row['frame']: index for index, row in enumerate(samples)}
    onset = frame_index[report['yellow_to_red_onset']['frame']]
    entry = report['first_body_entry']
    entry_index = None if entry is None else frame_index[entry['frame']]
    measured = None if entry_index is None else entry_index - onset
    requested = None if CASES[suffix] is None else CASES[suffix] - 160
    matched = measured == requested
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=True)
    for name, unit, key in (
        ('signal_state', 'text', 'signal_state'),
        ('ego_body_in_intersection', 'boolean', 'body_in_intersection'),
        ('ego_approach_speed', 'm/s', 'ego_speed_mps'),
    ):
        _write_jsonl(channels / (name + '.jsonl'), (
            {'frame': s['frame'], 'time_s': s['time_s'], 'value': s[key]} for s in samples))
    evidence = [
        {'name': name, 'unit': unit, 'reference': 'channels/' + name + '.jsonl'}
        for name, unit in (('signal_state', 'text'),
                           ('ego_body_in_intersection', 'boolean'),
                           ('ego_approach_speed', 'm/s'))
    ]
    result = {
        'case_id': case_id,
        'measured_values': {
            'yellow_to_red_onset': report['yellow_to_red_onset'],
            'first_body_entry': entry,
            'entry_minus_red_onset_frames': measured,
            'entry_minus_red_onset_s': report['entry_minus_red_onset_s'],
            'entry_with_red_exhibited_observed': report['entry_with_red_exhibited_observed'],
            'yellow_stop_feasibility_judgment': 'unresolved',
            'physical_head_visibility_judgment': 'unresolved',
        },
        'target_checks': [{
            'target': 'body_entry_relative_to_red_onset_frames',
            'requested': requested, 'measured': measured,
            'method': 'first original body polygon overlap minus first observed Yellow-to-Red original frame',
            'tolerance': 0, 'matched': matched,
            'physical_cause_confirmed': False,
            'cause_evidence': list(report['sources']),
        }],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source assessment pending',
        'physical_failure_flags': [
            'Native head visibility and yellow stopping feasibility require independent review'
        ],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': evidence,
        'source_evidence_hashes': report['sources'],
        'realized_observables': {},
    }
    try:
        from worker_exchange.native_output import physical_result, write_result
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
        from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {
        'format': 'worker-c158196-yellow-red-saved-analysis',
        'case_id': case_id,
        'measurements': {
            'entry_minus_red_onset_frames': measured,
            'entry_with_red_exhibited_observed': report['entry_with_red_exhibited_observed'],
            'target_matched': matched,
            'source_sha256': report['sources'],
        },
        'source_report': report,
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'yellow_stop_feasibility_judgment': 'unresolved',
        'physical_head_visibility_judgment': 'unresolved',
        'legal_conclusion': 'unresolved',
        'analysis_complete': True,
    }
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    return analysis


def attempt_case_prefix():
    return 'testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
