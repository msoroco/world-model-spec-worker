"""Finalize a retained paragraph (d) attempt from source files only."""
import argparse
import hashlib
import json
from pathlib import Path

import saved


REQUIRED = ('native-raw-actors.jsonl', 'video_frames.jsonl',
            'native-map-readback.json', 'native-capture-report.json',
            'review-source.json', 'road-source.xodr', 'overview.mkv',
            'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_paragraph_d(metric):
    value = {key: metric[key] for key in (
        'frames_joined', 'ego_body_right_of_lead_frames',
        'ego_body_ahead_and_right_of_lead_frames',
        'one_way_designation_reviewed', 'unobstructed_pavement_reviewed',
        'right_pass_pixels_reviewed', 'original_native_observed')}
    if 'curb_cone_position_frames' in metric:
        value['curb_cone_position_frames'] = metric['curb_cone_position_frames']
        value['obstruction_significance_reviewed'] = metric['obstruction_significance_reviewed']
    return value


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt), Path(output)
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    if sha(attempt / 'road-source.xodr') != sha(attempt / 'one-way-pass.xodr'):
        raise ValueError('Independent road source differs from selected construction')
    case_id = config['case_id']
    if not case_id.endswith(('__witness_1', '__witness_2')):
        raise ValueError('Unknown paragraph (d) selected case')
    construction = json.loads((attempt / 'construction.json').read_text())
    if construction['case_id'] != case_id:
        raise ValueError('Selected construction identity differs')
    review = json.loads((attempt / 'review-source.json').read_text())
    diagnostic = review.get('source_kind') == 'synthetic_fixture_review'
    metric = saved.measure(attempt, attempt, attempt / 'review-source.json',
                           synthetic_fixture=diagnostic)
    values = measure_paragraph_d(metric)
    hashes = {name: sha(attempt / name) for name in REQUIRED}
    contract = json.loads((attempt / 'measurement-contract.json').read_text())
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {}, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    for row in contract['requirements']:
        report['measurements'][row['output_key']] = {
            'method': row['method'], 'value': values,
            'sources': {name: hashes[name] for name in row['inputs']}}
    raw = [json.loads(row) for row in
           (attempt / 'native-raw-actors.jsonl').read_text().splitlines()]
    frames = [json.loads(row) for row in
              (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(raw) != 600 or len(frames) != 600:
        raise ValueError('Source frame count differs')
    evidence = []
    channels = attempt / 'channels'
    channels.mkdir()
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for actor, frame in zip(raw, frames):
                stream.write(json.dumps({'time_s': frame['time_s'],
                    'native_frame': frame['native_frame'],
                    'value': {'ego': actor['ego'], 'lead': actor['lead'],
                              'obstruction': actor.get('obstruction'),
                              'source_rgb_sha256': frame['source_rgb_sha256'],
                              'source_hashes': hashes}},
                    allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    context_path = channels / 'one_way_designation_source.json'
    context_path.write_text(json.dumps({'one_way_designation_source': {'reviewed': False, 'native_map_source': 'native-map-readback.json', 'reason': 'Independent designation review pending'}}, allow_nan=False) + '\n')
    evidence.append({'name': 'one_way_designation_source', 'unit': 'structured', 'reference': 'channels/one_way_designation_source.json'})
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-measured right-side pass',
                'requested': True,
                'measured': metric['ego_body_ahead_and_right_of_lead_frames'] > 0,
                'method': 'original frame-joined ego and lead bodies',
                'tolerance': 0,
                'matched': metric['ego_body_ahead_and_right_of_lead_frames'] > 0,
                'physical_cause_confirmed': False,
                'cause_evidence': list(REQUIRED)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame source analysis; physical and legal review pending',
              'physical_failure_flags': ['One-way designation, pavement condition and original pixels require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in saved.CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if diagnostic
                                  else 'original_native'), 'accepted': False}
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
