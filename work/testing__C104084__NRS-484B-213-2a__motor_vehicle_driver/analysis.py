"""Saved-only Native finalizer for the exact crest observations.

This consumes sealed acquisition files and emits derived Native outputs. The
source packets and original videos are never changed by this analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest import ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value)


def analyze(attempt_dir, *, assignment_id, case_id, expected_frames=900,
            recording_description=None):
    from scenario_pipeline.worker_exchange.native_output import frame_record, validate_result

    attempt = Path(attempt_dir).resolve()
    manifest = attempt / 'source-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original source manifest missing')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    required = set(REQUIRED_SOURCES)
    if case_id.endswith('__left_one_way_obstructed'):
        required.add(ONE_WAY_AUTHORITY)
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError('sealed original source manifest has wrong exact sources')
    observation = measure(attempt, hashes, case_id=case_id,
                          assignment_id=assignment_id, expected_frames=expected_frames)
    frame_rows = [json.loads(line) for line in (attempt / 'frames.jsonl').read_text().splitlines()]
    ray_rows = [json.loads(line) for line in (attempt / 'crest-rays.jsonl').read_text().splitlines()]
    if recording_description is None:
        config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
        recording_description = config['case']['recording_description']
    if not isinstance(recording_description, dict):
        raise ValueError('recording description is missing')
    for name in ('trace.jsonl', 'video_frames.jsonl', 'result.json'):
        if (attempt / name).exists():
            raise ValueError('retain prior derived output; choose a fresh analysis stage')

    trace = []
    mapping = []
    for index, (body, ray) in enumerate(zip(frame_rows, ray_rows)):
        frame = body['frame']
        time_s = body['timestamp_s']
        trace.append({'frame': frame, 'time_s': time_s,
                      'ego_body_corners_signed_m': body['ego_body_corners_signed_m'],
                      'opposing_body_distance_m': body['opposing_body_distance_m'],
                      'opposing_body_corner_ray_hits': ray['body_corner_ray_hits']})
        mapping.append(frame_record(index, frame, time_s,
                                    camera_frames={name: frame for name in
                                                   ('forward', 'left', 'right', 'rear')}))

    expected_left = not case_id.endswith('__right_crest_obstructed')
    expected_blocked = not case_id.endswith('__left_crest_clear')
    measured_left = bool(observation['ego_body_left_side_frames'])
    measured_blocked = bool(observation['all_corner_rays_blocked_frames'])
    checks = []
    for target, requested, measured in (
            ('left-side body motion', expected_left, measured_left),
            ('all-corner proxy-ray blockage', expected_blocked, measured_blocked),
            ('body and view condition on one original frame', True,
             bool(observation['body_and_view_target_frames']))):
        checks.append({'target': target, 'requested': requested,
                       'measured': measured, 'method': 'sealed Native body/ray/frame join',
                       'tolerance': 0, 'matched': requested == measured,
                       'physical_cause_confirmed': False,
                       'cause_evidence': observation['source_sha256']})
    result = {'case_id': case_id, 'measured_values': observation,
              'target_checks': checks, 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Original crest packets measured; physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [f'camera-{name}.mp4' for name in
                                   ('forward', 'left', 'right', 'rear')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': recording_description,
              'recording_evidence': [], 'realized_observables': {}}
    validate_result(result)
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('original source manifest changed during analysis')
    if any(hashlib.sha256((attempt / name).read_bytes()).hexdigest() != digest
           for name, digest in hashes.items()):
        raise ValueError('original source changed during analysis')
    _write_new(attempt / 'trace.jsonl', ''.join(json.dumps(row, sort_keys=True) + '\n' for row in trace))
    _write_new(attempt / 'video_frames.jsonl', ''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping))
    _write_new(attempt / 'result.json', json.dumps(result, indent=2, sort_keys=True) + '\n')
    return {'format': 'c104084-crest-saved-analysis-v1',
            'case_id': case_id, 'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'observation': observation, 'native_result': 'result.json',
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt, assignment_id=args.assignment, case_id=args.case)
    _write_new(Path(args.output), json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
