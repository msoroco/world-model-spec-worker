"""Saved-only source join and measurement for LVMC 11.20.070.

The four camera streams are retained by the Native attempt and decoded by the
independent delivery audit.  This finalizer never treats a diagnostic as proof
of physical or legal obstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from space_measure import analyze as measure_space

SOURCES = ('space_scene.json', 'space_frames.jsonl', 'video_frames.jsonl', 'trace.jsonl')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def analyze(attempt):
    root = Path(attempt)
    for name in SOURCES + ('config.json',):
        if not (root / name).is_file() or not (root / name).read_bytes():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((root / 'config.json').read_text())
    scene = json.loads((root / 'space_scene.json').read_text())
    frames = read_rows(root / 'space_frames.jsonl')
    mapping = read_rows(root / 'video_frames.jsonl')
    trace = read_rows(root / 'trace.jsonl')
    if not frames or len(mapping) != len(frames) or len(trace) != len(frames):
        raise ValueError('Original source frame counts differ')
    for index, (row, video, state) in enumerate(zip(frames, mapping, trace)):
        if (row.get('frame') != index or video.get('video_frame') != index
                or video.get('carla_frame') != state.get('frame')
                or row.get('carla_frame') != state.get('frame')
                or row.get('time_s') != video.get('time_s')
                or row.get('time_s') != state.get('time_s')):
            raise ValueError('Original body, trace and camera frame join differs')
    if scene.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Original scene selects another exact case')
    measurement = measure_space(scene, frames)
    entry = measurement['entry']
    passage_by_frame = {}
    for item in measurement['passage_occupancies']:
        passage_by_frame[item['frame']] = max(
            passage_by_frame.get(item['frame'], 0.0), item['ego_overlap_area_m2'])
    values = {
        'entry_frame_and_region': [(row['frame'], row['time_s'], float(row['frame'] == entry['frame']))
                                   for row in frames],
        'downstream_available_length': [(entry['frame'], entry['time_s'], entry['downstream_available_length_m'])],
        'passage_obstruction': [(row['frame'], row['time_s'], passage_by_frame.get(row['frame'], 0.0))
                                for row in frames],
        'signal_indication': [(row['frame'], row['time_s'], float(row['signal_state'] == 'proceed'))
                              for row in frames],
    }
    for name, samples in values.items():
        (root / (name + '.jsonl')).write_text(''.join(
            json.dumps({'frame': frame, 'time_s': time_s, 'value': value}) + '\n'
            for frame, time_s, value in samples))
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {'space_at_entry': {'method': 'analyze',
                                                 'value': measurement,
                                                 'sources': {name: sha(root / name) for name in SOURCES}}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    measured = report['measurements']['space_at_entry']['value']
    names = [channel['name'] for channel in config['case']['recording_description']['channels']]
    expected = ('entry_frame_and_region', 'downstream_available_length',
                'passage_obstruction', 'signal_indication')
    if set(names) != set(expected):
        raise ValueError('Exact recording channels differ')
    recorded = []
    realized = {}
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        path = root / (name + '.jsonl')
        rows = read_rows(path)
        if not rows:
            raise ValueError('Derived channel missing: ' + name)
        recorded.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name, 'sha256': sha(path)})
        realized[name] = {'unit': channel['unit'], 'method': channel['method'],
                          'time_window': channel['time_window'],
                          'statistic': 'original sampled values', 'reference': path.name,
                          'value': [row['value'] for row in rows],
                          'sample_window_s': [rows[0]['time_s'], rows[-1]['time_s']]}
    return {'case_id': report['case_id'], 'measured_values': {'space_at_entry': measured},
            'target_checks': [{'target': 'space available beyond actual entry and passage occupation',
                               'requested': report['case_id'], 'measured': measured,
                               'method': 'original-frame geometry and participant passage join',
                               'tolerance': None, 'matched': True,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Raw Native source review required after capture'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved source measurement complete; physical and legal outcome unverified',
            'physical_failure_flags': {'motion_unverified': True, 'obstruction_judgment_unverified': True},
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in CAMERAS],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': config['case']['recording_description'],
            'recording_evidence': recorded, 'realized_observables': realized,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    out = Path(args.output)
    if out.exists():
        raise ValueError('Retain prior analysis report')
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, result(args.attempt, report))


if __name__ == '__main__':
    main()
