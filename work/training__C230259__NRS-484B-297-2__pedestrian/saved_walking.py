"""Saved-only walking-side measurements from retained source files.

These measurements describe the scene; they do not decide a legal outcome.
"""

import argparse
import hashlib
import json
from pathlib import Path

from walking_side import FRAMES, measure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_file(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_walk_side(context, trace):
    return measure(context, trace)['counts']


def measure_scope(context, trace):
    return {'highway_authority_source': context['highway_authority_source'],
            'highway_boundary_source': context['highway_boundary_source'],
            'sidewalk_inventory_source': context['sidewalk_inventory_source'],
            'pedestrian_id': trace[0]['pedestrian_id'],
            'no_sidewalk_sourced': context['sidewalk_present'] is False}


def measure_exception(context, trace):
    return {'subsection_6_obstruction_source': context['subsection_6_obstruction_source'],
            'obstruction_exception_active': context['subsection_6_obstruction'],
            'source_frames': len(trace)}


def ensure_recording_channels(attempt, original_trace):
    """Rebuild derived channel copies from the retained original trace."""
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, value in (('kin.position', lambda row: row['position_m']),
                        ('kin.speed', lambda row: row['speed_mps'])):
        expected = [{'time_s': row['time_s'], 'value': value(row)} for row in original_trace]
        path = channel_dir / (name + '.jsonl')
        if path.is_file():
            if rows(path) != expected:
                raise ValueError('Recording channel disagrees with original trace: ' + name)
        else:
            path.write_text(''.join(json.dumps(row) + '\n' for row in expected))


def finalize(attempt):
    attempt = Path(attempt)
    config = json.loads(require_file(attempt, 'config.json').read_text())
    context_path = require_file(attempt, 'reviewed-road-source.json')
    trace_path = require_file(attempt, 'walking-source.jsonl')
    frame_path = require_file(attempt, 'video_frames.jsonl')
    context = json.loads(context_path.read_text())
    trace = rows(trace_path)
    frame_map = rows(frame_path)
    original_trace = rows(require_file(attempt, 'trace.jsonl'))
    if len(trace) != FRAMES or len(frame_map) != FRAMES:
        raise ValueError('Incomplete original source/frame window')
    if len(original_trace) != FRAMES:
        raise ValueError('Incomplete original trace window')
    for sample, frame in zip(trace, frame_map):
        if sample.get('video_frame') != frame.get('video_frame') or sample.get('native_frame') != frame.get('native_frame'):
            raise ValueError('Walking trace and original frame map differ')
        if abs(sample.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6:
            raise ValueError('Walking trace and frame time differ')
    for sample, original in zip(trace, original_trace):
        if sample['native_frame'] != original['frame'] or abs(sample['time_s'] - original['time_s']) > 1e-6:
            raise ValueError('Walking source and original trace differ')
    ensure_recording_channels(attempt, original_trace)
    native_path = attempt / 'result.json'
    if not native_path.is_file():
        marker = json.loads(require_file(attempt, 'acquisition-provenance.json').read_text())
        if marker.get('provenance_kind') != 'synthetic_fixture' or marker.get('diagnostic_fixture') is not True:
            raise ValueError('Original Native result missing; only explicit synthetic fixtures may generate a diagnostic result')
        from worker_exchange.native_output import physical_result, write_result
        counts = measure(context, trace)['counts']
        target_side = 'traffic_left' if config['condition'] == 'a' else 'traffic_right'
        result = {'case_id': config['case_id'], 'measured_values': counts,
                  'target_checks': [{'target': 'continuous requested side and opposing heading',
                                     'requested': {'side': target_side, 'frames': FRAMES},
                                     'measured': {'side_frames': counts[target_side],
                                                  'opposing_heading_frames': counts['facing_opposite_traffic']},
                                     'method': 'synthetic diagnostic source trace', 'tolerance': 0,
                                     'matched': counts[target_side] == counts['facing_opposite_traffic'] == FRAMES,
                                     'physical_cause_confirmed': False,
                                     'cause_evidence': 'walking-source.jsonl; fixture only'}],
                  'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
                  'termination_reason': 'Synthetic diagnostic source only',
                  'physical_failure_flags': {'original_native_unobserved': True},
                  'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'],
                  'video_frame_map_reference': 'video_frames.jsonl',
                  'recording_description': config['recording_description'],
                  'recording_evidence': [{'name': item['name'], 'unit': item['unit'],
                                          'reference': 'channels/' + item['name'] + '.jsonl'}
                                         for item in config['recording_description']['channels']] +
                                        [{'name': 'highway_boundary_source', 'unit': 'structured',
                                          'reference': 'reviewed-road-source.json'}],
                  'realized_observables': {}}
        write_result(attempt, physical_result(attempt, result))
    native = json.loads(native_path.read_text())
    diagnostic = native.get('diagnostic_fixture') is True and native.get('provenance_kind') == 'synthetic_fixture'
    if context.get('source_kind') != ('synthetic_diagnostic' if diagnostic else 'original_native'):
        raise ValueError('Road context provenance differs from Native result')
    if config.get('case_id') not in config.get('selected_case_ids', []):
        raise ValueError('Wrong saved case identity')
    sources = {name: digest(attempt / name) for name in ('reviewed-road-source.json', 'walking-source.jsonl', 'video_frames.jsonl')}
    observations = measure(context, trace)
    return {'format': 'worker-analysis-report', 'case_id': config['case_id'],
            'source_kind': context['source_kind'], 'diagnostic_fixture': diagnostic,
            'analysis_complete': True, 'physical_completion': False, 'legal_verdict': None,
            'measurements': {'walking_side_trace': {'method': 'measure_walk_side',
                                                    'value': measure_walk_side(context, trace), 'sources': sources},
                             'highway_walk_scope': {'method': 'measure_scope',
                                                    'value': measure_scope(context, trace), 'sources': sources},
                             'subsection_6_exclusion': {'method': 'measure_exception',
                                                        'value': measure_exception(context, trace), 'sources': sources}},
            'frame_count': FRAMES, 'observations': observations,
            'limitations': ['Legal outcome and original physical realization require independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'frames': result['frame_count'],
                      'counts': result['measurements']['walking_side_trace']['value']}))
