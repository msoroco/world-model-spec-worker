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


def finalize(attempt):
    attempt = Path(attempt)
    config = json.loads(require_file(attempt, 'config.json').read_text())
    native = json.loads(require_file(attempt, 'result.json').read_text())
    context_path = require_file(attempt, 'reviewed-road-source.json')
    trace_path = require_file(attempt, 'walking-source.jsonl')
    frame_path = require_file(attempt, 'video_frames.jsonl')
    context = json.loads(context_path.read_text())
    trace = rows(trace_path)
    frame_map = rows(frame_path)
    if len(trace) != FRAMES or len(frame_map) != FRAMES:
        raise ValueError('Incomplete original source/frame window')
    for sample, frame in zip(trace, frame_map):
        if sample.get('video_frame') != frame.get('video_frame') or sample.get('native_frame') != frame.get('native_frame'):
            raise ValueError('Walking trace and original frame map differ')
        if abs(sample.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6:
            raise ValueError('Walking trace and frame time differ')
    diagnostic = native.get('diagnostic_fixture') is True and native.get('provenance_kind') == 'synthetic_fixture'
    if context.get('source_kind') != ('synthetic_diagnostic' if diagnostic else 'original_native'):
        raise ValueError('Road context provenance differs from Native result')
    if config.get('case_id') not in config.get('selected_case_ids', []):
        raise ValueError('Wrong saved case identity')
    measurements = measure(context, trace)
    sources = {name: digest(attempt / name) for name in ('reviewed-road-source.json', 'walking-source.jsonl', 'video_frames.jsonl')}
    return {'format': 'worker-analysis-report', 'case_id': config['case_id'],
            'source_kind': context['source_kind'], 'diagnostic_fixture': diagnostic,
            'analysis_complete': True, 'physical_completion': False, 'legal_verdict': None,
            'measurements': {'walking_side_trace': {'method': 'finalize', 'value': measurements['counts'],
                                                    'sources': sources}},
            'frame_count': FRAMES, 'observations': measurements,
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
