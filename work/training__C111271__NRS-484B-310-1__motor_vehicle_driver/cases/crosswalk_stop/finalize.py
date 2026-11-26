"""Saved-only source measurement for the flashing-red stop comparison."""

import argparse
import hashlib
import json
from pathlib import Path

from capture import derive_channels
from measure import measure

SOURCES = ('native.jsonl', 'video_frames.jsonl', 'geometry.json')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flashing_red_stop(folder, paths):
    return measure(Path(folder) / 'config.json', *paths)


def analysis_report(folder):
    folder = Path(folder)
    cfg = json.loads(required(folder, 'config.json').read_text())
    paths = [required(folder, name) for name in SOURCES]
    measured = flashing_red_stop(folder, paths)
    if measured['case_id'] != cfg['selected_case_id'] or measured['frames'] != 600:
        raise ValueError('Exact selected case or frame count differs')
    if measured['stopping_reference'] != cfg['reference_kind']:
        raise ValueError('Selected stopping-reference hierarchy differs')
    return {'format': 'worker-c111271-flashing-red-analysis-v1',
            'case_id': cfg['selected_case_id'], 'analysis_complete': True,
            'legal_verdict_claimed': False,
            'measurements': {'flashing_red_stop': {
                'method': 'flashing_red_stop', 'value': measured,
                'sources': {name: sha(folder / name) for name in SOURCES}}},
            'limitations': ['Full legal stop is not defined by the 0.05 m/s engineering detector.',
                            'Official designation, signal governance and post-stop right to proceed require independent source review.',
                            'Software fixture pixels and motion cannot establish physical acceptance.']}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh analysis path; retain original sources')
    cfg = json.loads(required(attempt, 'config.json').read_text())
    if cfg.get('rate_hz') != 20 or cfg.get('duration_s') != 30:
        raise ValueError('Exact 600-frame source contract changed')
    report = analysis_report(attempt)
    facts = report['measurements']['flashing_red_stop']['value']
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    result = {
        'case_id': cfg['selected_case_id'], 'measured_values': facts,
        'target_checks': [{
            'target': 'flashing red, applicable reference, pre-reference halt and post-stop yield',
            'requested': {'halt': cfg['requested_halt'], 'reference_kind': cfg['reference_kind']},
            'measured': {'halt_runs': facts['pre_reference_halt_runs'],
                         'first_crossing_frame': facts['first_crossing_frame'],
                         'conflict_after_crossing': facts['conflict_occupied_after_crossing_frames']},
            'method': 'original frame-joined Native signal, body and conflict sources',
            'tolerance': 'engineering source diagnostic only; legal review pending',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': original,
        'maneuver_completed': False,
        'termination_reason': 'independent physical and legal source review pending',
        'physical_failure_flags': ['official_device_and_governance_review_pending',
                                   'full_stop_and_post_stop_yield_review_pending'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': derive_channels(attempt),
        'realized_observables': {'pre_reference_halt_frames': {
            'value': facts['stopped_before_reference_frames'], 'unit': 'frames',
            'method': 'source-joined engineering halt detector',
            'time_window': '600 frames', 'statistic': 'count',
            'reference': 'native.jsonl'}},
        'accepted': False, 'legal_verdict_claimed': False}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
